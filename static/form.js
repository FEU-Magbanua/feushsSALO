const $ = id => document.getElementById(id);
const SIMPLE = ["student_id","grade_section","pathway","adviser","semester","subject","subject_teacher","date_identified",
 "referral_reason","melc","gap","target","b_type","b_date","b_score","b_total","b_remarks",
 "f_type","f_date","f_score","f_total","f_remarks","teacher_remarks"];
let editId = DATA ? DATA.id : null;

function snack(msg){const s=$("snack");s.textContent=msg;s.classList.add("on");setTimeout(()=>s.classList.remove("on"),2800);}

/* proficiency computed from percentage */
function calc(p){
  const s=parseFloat($(p+"_score").value), t=parseFloat($(p+"_total").value);
  const pct=$(p+"_pct"), lv=$(p+"_level");
  if(isNaN(s)||isNaN(t)||t<=0||s<0||s>t){
    pct.textContent="—"; lv.textContent=(s>t)?"Score exceeds maximum":"Proficiency level"; lv.className="chip"; return;}
  const v=Math.round(s/t*1000)/10;
  const level=LEVELS.find(l=>v>=l.min_pct)||LEVELS[LEVELS.length-1];
  pct.textContent=v+"%"; lv.textContent=level.name;
  lv.className="chip lv-"+level.name.split(" ")[0].toLowerCase();
}
["b","f"].forEach(p=>["score","total"].forEach(k=>$(p+"_"+k).addEventListener("input",()=>calc(p))));

$("student_id").addEventListener("change",e=>{
  const o=e.target.selectedOptions[0]; $("student_no").value=o?o.dataset.no||"":"";});

/* F: only one decision at a time */
document.querySelectorAll(".dec").forEach(c=>c.addEventListener("change",()=>{
  if(c.checked) document.querySelectorAll(".dec").forEach(o=>{if(o!==c)o.checked=false;});}));

/* D: support sessions */
function opt(list,val){return '<option value="">Select…</option>'+list.map(x=>`<option${x===val?" selected":""}>${x}</option>`).join("");}
function addSupport(r={}){
  const d=document.createElement("div"); d.className="srow";
  const esc=v=>(v||"").replace(/"/g,"&quot;");
  d.innerHTML=`<div class="grid">
   <label class="field"><input type="date" data-k="date" value="${esc(r.date)}"><span>Date</span></label>
   <label class="field"><input data-k="type" value="${esc(r.type)}"><span>Type of support</span></label>
   <label class="field"><input data-k="topic" value="${esc(r.topic)}"><span>Topic / focus</span></label>
   <label class="field"><select data-k="facilitated_by">${opt(OPTS.facilitator,r.facilitated_by)}</select><span>Facilitated by</span></label>
   <label class="field"><select data-k="mode">${opt(OPTS.mode,r.mode)}</select><span>Mode</span></label>
   <label class="check"><input type="checkbox" data-k="completed"${r.completed?" checked":""}>Attended / completed</label></div>
   <div class="tools"><span></span><button type="button" class="btn danger">Remove</button></div>`;
  d.querySelector(".danger").onclick=()=>d.remove();
  $("supports").appendChild(d);
}
$("addSupport").onclick=()=>addSupport();

/* add student dialog */
$("addStu").onclick=()=>$("stuDlg").showModal();
$("ns_cancel").onclick=()=>$("stuDlg").close();
$("ns_save").onclick=async()=>{
  const r=await fetch("/api/students",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({student_no:$("ns_no").value,name:$("ns_name").value})});
  const j=await r.json(); if(!r.ok){snack(j.error);return;}
  const o=new Option(j.name,j.id); o.dataset.no=j.student_no; $("student_id").add(o);
  $("student_id").value=j.id; $("student_no").value=j.student_no; $("stuDlg").close();
  $("ns_no").value=$("ns_name").value="";
};

/* load existing */
if(DATA){
  SIMPLE.forEach(k=>{if(DATA[k]!=null)$(k).value=DATA[k];});
  $("student_no").value=DATA.student_no;
  if(DATA.decision) document.querySelector(`.dec[value="${DATA.decision}"]`).checked=true;
  DATA.supports.forEach(addSupport);
} else { addSupport(); $("date_identified").valueAsDate=new Date(); }
calc("b"); calc("f");

async function save(){
  if(!$("student_id").value){$("student_id").closest(".field").classList.add("err");snack("Select a student first.");$("student_id").focus();return null;}
  const body={id:editId};
  SIMPLE.forEach(k=>body[k]=$(k).value);
  const dec=document.querySelector(".dec:checked"); body.decision=dec?dec.value:"";
  body.supports=[...document.querySelectorAll(".srow")].map(r=>{
    const o={}; r.querySelectorAll("[data-k]").forEach(i=>o[i.dataset.k]=i.type==="checkbox"?i.checked:i.value); return o;});
  const r=await fetch("/api/passports",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await r.json(); if(!r.ok){snack(j.error||"Could not save.");return null;}
  editId=j.id; return j.id;
}
$("saveBtn").onclick=async()=>{if(await save()!==null){snack("Passport saved");setTimeout(()=>location.href="/",900);}};
$("printBtn").onclick=async()=>{const id=await save(); if(id!==null){snack("Saved. Opening PDF view…");window.open(`/passport/${id}/print?auto=1`,"_blank");}};

/* Filter grade section based on the selected pathway */
$("pathway").addEventListener("change", e => {
  const selectedPathway = e.target.value.trim();
  const sectionSelect = $("grade_section");
  
  // Disable the section dropdown entirely if no pathway is selected
  sectionSelect.disabled = !selectedPathway;

  Array.from(sectionSelect.options).forEach((opt, idx) => {
    // Skip the default "Select…" option created by the Jinja macro
    if (idx === 0) return; 
    
    // Check if the option text starts with the selected pathway (e.g., "BAE")
    const isMatch = opt.value.startsWith(selectedPathway);
    
    // Use both hidden and disabled for maximum browser compatibility
    opt.hidden = !isMatch;
    opt.disabled = !isMatch;
    
    // Clear the section selection if the current choice is no longer valid
    if (!isMatch && opt.selected) {
      sectionSelect.value = "";
    }
  });
});

// Trigger the filter immediately on page load so existing data renders correctly
$("pathway").dispatchEvent(new Event("change"));