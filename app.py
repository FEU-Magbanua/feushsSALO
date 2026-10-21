import os
import sqlite3
from datetime import datetime

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "salo.db")
SCHOOL_YEAR = "2026 – 2027"

app = Flask(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY, category TEXT NOT NULL, value TEXT NOT NULL,
    sort INTEGER DEFAULT 0, UNIQUE(category, value));
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY, student_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, min_pct REAL NOT NULL);
CREATE TABLE IF NOT EXISTS passports (
    id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
    grade_section TEXT, pathway TEXT, adviser TEXT, semester TEXT, subject TEXT,
    subject_teacher TEXT, date_identified TEXT, referral_reason TEXT,
    melc TEXT, gap TEXT, target TEXT,
    b_type TEXT, b_date TEXT, b_score REAL, b_total REAL, b_remarks TEXT,
    f_type TEXT, f_date TEXT, f_score REAL, f_total REAL, f_remarks TEXT,
    decision TEXT, teacher_remarks TEXT,
    created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS supports (
    id INTEGER PRIMARY KEY,
    passport_id INTEGER NOT NULL REFERENCES passports(id) ON DELETE CASCADE,
    date TEXT, type TEXT, topic TEXT, facilitated_by TEXT, mode TEXT, completed INTEGER DEFAULT 0);
"""


LEVELS = [("Beginning", 0), ("Developing", 50), ("Approaching Proficiency", 65),
          ("Proficient", 80), ("Advanced", 90)]
DECISIONS = {"recovered": "Competency Recovered", "continue": "Continue Intervention",
             "enrichment": "For Enrichment", "refer": "Refer to Guidance / Other Services"}

FIELDS = ["student_id", "grade_section", "pathway", "adviser", "semester", "subject",
          "subject_teacher", "date_identified", "referral_reason", "melc", "gap", "target",
          "b_type", "b_date", "b_score", "b_total", "b_remarks",
          "f_type", "f_date", "f_score", "f_total", "f_remarks", "decision", "teacher_remarks"]
NUMERIC = {"b_score", "b_total", "f_score", "f_total"}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()



def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM levels LIMIT 1").fetchone():
        conn.executemany("INSERT INTO levels(name,min_pct) VALUES(?,?)", LEVELS)
    if not conn.execute("SELECT 1 FROM students LIMIT 1").fetchone():
        conn.execute("INSERT INTO students(student_no, name) VALUES(?,?)", ("00000", "TEST STUDENT"))
    conn.commit()
    conn.close()

def get_options():
    out = {}
    for r in db().execute("SELECT category,value FROM options ORDER BY category,sort,id"):
        out.setdefault(r["category"], []).append(r["value"])
    return out


def get_levels():
    return [dict(r) for r in db().execute("SELECT name,min_pct FROM levels ORDER BY min_pct DESC")]


def score_info(score, total):
    if score is None or not total:
        return None, ""
    pct = round(score / total * 100, 1)
    for lv in get_levels():
        if pct >= lv["min_pct"]:
            return pct, lv["name"]
    return pct, ""


def get_passport(pid):
    row = db().execute(
        "SELECT p.*, s.name AS student_name, s.student_no FROM passports p "
        "JOIN students s ON s.id=p.student_id WHERE p.id=?", (pid,)).fetchone()
    if not row:
        return None
    p = dict(row)
    for k in ("b", "f"):
        p[k + "_pct"], p[k + "_level"] = score_info(p[k + "_score"], p[k + "_total"])
    p["supports"] = [dict(r) for r in db().execute(
        "SELECT * FROM supports WHERE passport_id=? ORDER BY date,id", (pid,))]
    return p


@app.template_filter("fdate")
def fdate(v):
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
    except (TypeError, ValueError):
        return v or ""


@app.template_filter("num")
def num(v):
    return "" if v is None else "%g" % v


@app.route("/")
def landing():
    rows = db().execute(
        "SELECT p.id, p.subject, p.grade_section, p.pathway, p.date_identified, p.decision, "
        "p.updated_at, s.name, s.student_no FROM passports p JOIN students s ON s.id=p.student_id "
        "ORDER BY p.updated_at DESC").fetchall()
    return render_template("index.html", rows=rows, decisions=DECISIONS)


@app.route("/passport/new")
def new_passport():
    return render_template("form.html", data=None, **form_ctx())


@app.route("/passport/<int:pid>/edit")
def edit_passport(pid):
    p = get_passport(pid)
    if not p:
        return redirect(url_for("landing"))
    return render_template("form.html", data=p, **form_ctx())


def form_ctx():
    students = [dict(r) for r in db().execute("SELECT id,student_no,name FROM students ORDER BY name")]
    return dict(opts=get_options(), students=students, levels=get_levels(),
                decisions=DECISIONS, school_year=SCHOOL_YEAR)


@app.route("/passport/<int:pid>/print")
def print_passport(pid):
    p = get_passport(pid)
    if not p:
        return redirect(url_for("landing"))
    opts = get_options()
    return render_template("print.html", p=p, reasons=opts["referral"], decisions=DECISIONS,
                           director=opts["director"][0], school_year=SCHOOL_YEAR,
                           grade=(p["grade_section"] or "")[:8])


@app.post("/api/passports")
def save_passport():
    d = request.get_json(force=True)
    if not d.get("student_id"):
        return jsonify(error="Select a student first."), 400
    vals = []
    for f in FIELDS:
        v = d.get(f)
        if v in ("", None):
            v = None
        elif f in NUMERIC:
            v = float(v)
        vals.append(v)
    now = datetime.now().isoformat(timespec="seconds")
    conn = db()
    pid = d.get("id")
    if pid:
        sets = ",".join(f"{f}=?" for f in FIELDS)
        conn.execute(f"UPDATE passports SET {sets}, updated_at=? WHERE id=?", vals + [now, pid])
        conn.execute("DELETE FROM supports WHERE passport_id=?", (pid,))
    else:
        cols = ",".join(FIELDS)
        qs = ",".join("?" * (len(FIELDS) + 2))
        pid = conn.execute(f"INSERT INTO passports({cols},created_at,updated_at) VALUES({qs})",
                           vals + [now, now]).lastrowid
    for s in d.get("supports", []):
        if any(s.get(k) for k in ("date", "type", "topic")):
            conn.execute(
                "INSERT INTO supports(passport_id,date,type,topic,facilitated_by,mode,completed) "
                "VALUES(?,?,?,?,?,?,?)",
                (pid, s.get("date"), s.get("type"), s.get("topic"), s.get("facilitated_by"),
                 s.get("mode"), 1 if s.get("completed") else 0))
    conn.commit()
    return jsonify(id=pid)


@app.delete("/api/passports/<int:pid>")
def delete_passport(pid):
    db().execute("DELETE FROM passports WHERE id=?", (pid,))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/students")
def add_student():
    d = request.get_json(force=True)
    no, name = (d.get("student_no") or "").strip(), (d.get("name") or "").strip().upper()
    if not no or not name:
        return jsonify(error="Student number and name are required."), 400
    try:
        sid = db().execute("INSERT INTO students(student_no,name) VALUES(?,?)", (no, name)).lastrowid
        db().commit()
    except sqlite3.IntegrityError:
        return jsonify(error="That student number already exists."), 409
    return jsonify(id=sid, student_no=no, name=name)


init_db()
if __name__ == "__main__":
    app.run(port = 5000)
