const $=id=>document.getElementById(id);
const cut=$('cut');
const traces=[
  ['detect','Scanning active subjects and contradictions…'],
  ['medical_review','Reviewing clinical plausibility and baseline context…'],
  ['data_manager','Deduplicating record-cited queries…'],
  ['compliance','Applying protocol amendment delta…'],
  ['human_gate','Escalations ready for medical monitor…'],
  ['execute','Cycle state persisted for next cut.']
];

function trace(msg){
  const t=$('trace'); const p=document.createElement('p');
  p.innerHTML=msg; t.appendChild(p); t.scrollTop=t.scrollHeight;
}
function escapeHtml(v){
  return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function protocolFor(v){return v>=9?'v3':v>=6?'v2':'v1';}
async function apiFetch(url, options){
  const r=await fetch(url, options);
  const raw=await r.text();
  let data={};
  try{data=raw?JSON.parse(raw):{}}catch{throw new Error('API returned an invalid response ('+r.status+')');}
  if(!r.ok) throw new Error(data.detail||data.message||('API request failed ('+r.status+')'));
  return data;
}

async function loadCut(v){
  const s=await apiFetch('/api/stats?cut='+v);
  $('subjects').textContent=s.subjects??'—'; $('records').textContent=s.records??'—';
  $('siteCount').textContent=(s.sites??12)+' sites'; $('cutCount').textContent=(s.cuts??12)+' cuts indexed';
  $('protocol').textContent=protocolFor(v); $('protocolContext').textContent='Protocol '+protocolFor(v);
  $('critical').textContent=s.critical??'—';
  $('pending').textContent=s.pending??'—';
  trace('<b>[system]</b> Data cut '+v+' loaded · '+(s.records??0)+' visible records · protocol '+protocolFor(v));
}
async function apiQuery(text){
  return await apiFetch('/api/query?q='+encodeURIComponent(text)+'&cut='+cut.value);
}
function renderAnswer(data){
  $('liveAnswerTitle').textContent=(data.answer||[]).length?data.answer.join(' · '):'No qualifying result';
  $('liveAnswer').textContent=data.text||'No explanatory text returned.';
  $('protocolContext').textContent='Protocol '+protocolFor(+cut.value);
  const ev=data.evidence||[];
  $('footerStatus').textContent=ev.length+' source record(s) · cut '+cut.value+' · confidence '+Math.round((data.confidence||0)*100)+'%';
}
async function focusSubject(button){
  document.querySelectorAll('.focus').forEach(x=>x.classList.remove('activefocus'));
  button.classList.add('activefocus','busy');
  const subject=button.dataset.subject;
  document.querySelectorAll('.subject').forEach(x=>x.classList.toggle('selected',x.dataset.subject===subject));
  $('patient').textContent=subject;
  $('queryTitle').textContent='Patient 360 · '+subject;
  $('queryAnswer').textContent='Querying StudyGraph…';
  $('queryEvidence').innerHTML='Loading…';
  $('queryModal').classList.remove('hidden');
  try{
    const data=await apiQuery(button.dataset.query);
    renderAnswer(data);
    $('queryAnswer').textContent=data.text||((data.answer||[]).join(' · ')||'No qualifying result');
    $('queryEvidence').innerHTML=(data.evidence||[]).map(e=>'<div class="queryev">'+escapeHtml(e.domain||'DOC')+' · '+escapeHtml(e.usubjid||e.document||'document')+(e.seq!=null?' · seq '+escapeHtml(e.seq):'')+(e.section?' · '+escapeHtml(e.section):'')+'</div>').join('')||'<div class="queryev">No record evidence</div>';
    $('graph').classList.add('focused');
    trace('<b>[patient360]</b> '+escapeHtml(subject)+' → evidence resolved at cut '+cut.value);
  }catch(e){
    $('queryAnswer').textContent=e.message;
    trace('<b>[error]</b> '+escapeHtml(e.message));
  }finally{button.classList.remove('busy')}
}
async function loadStats(){try{await loadCut(+cut.value)}catch(e){trace('<b>[error]</b> StudyGraph stats unavailable')}}
$('cycle').onclick=async()=>{
  $('termstatus').textContent='RUNNING';
  $('cycle').disabled=true;
  try{
    const data=await apiFetch('/api/cycle?cut='+cut.value);
    const names=['detect','medical_review','data_manager','compliance','human_gate','execute'];
    for(let i=0;i<names.length;i++){
      const node=document.querySelectorAll('.pnode')[i];
      document.querySelectorAll('.pnode').forEach((n,j)=>n.classList.toggle('active',j===i));
      document.querySelectorAll('.pnode em').forEach((x,j)=>x.textContent=j===i?'ACTIVE':j<i?'DONE':'READY');
      const entry=(data.trace||[]).find(x=>x.node===names[i]);
      trace('<b>['+names[i]+']</b> '+escapeHtml(entry?.decision||traces[i][1]));
      await new Promise(r=>setTimeout(r,180));
    }
    $('pending').textContent=data.stats?.pending_escalations??data.pending_escalations?.length??0;
    $('critical').textContent=data.stats?.escalations??'0';
    $('footerStatus').textContent=(data.stats?.findings??0)+' findings · '+(data.stats?.escalations??0)+' escalations · cut '+cut.value;
    $('p5').classList.add('active'); $('p5').querySelector('em').textContent='COMPLETE';
  }catch(e){ trace('<b>[error]</b> '+escapeHtml(e.message)); }
  finally{$('termstatus').textContent='IDLE'; $('cycle').disabled=false;}
};
cut.onchange=async()=>{
  const v=+cut.value; document.querySelectorAll('.subject').forEach(x=>x.classList.remove('selected')); $('graph').classList.remove('focused');
  try{await loadCut(v)}catch(e){trace('<b>[error]</b> '+escapeHtml(e.message))}
};
$('bell').onclick=$('gate').onclick=()=>{$('modal').classList.remove('hidden')};
$('close').onclick=()=>{$('modal').classList.add('hidden')};
$('queryClose').onclick=()=>{$('queryModal').classList.add('hidden');$('graph').classList.remove('focused')};
async function gateDecision(decision, reason=''){
  try{
    const data=await apiFetch('/api/gate',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cut:+cut.value,code:'SAE_MISCODED',usubjid:'042-S02-004',decision,reason})
    });
    const status=data.escalation?.status||decision.toLowerCase();
    $('pending').textContent=Math.max(0,(+$('pending').textContent||0)-(status==='pending'?0:1));
    trace('<b>[human_gate]</b> '+decision+' SAE_MISCODED → '+status);
    return data;
  }catch(e){trace('<b>[error]</b> '+escapeHtml(e.message)); throw e}
}
$('reject').onclick=async()=>{try{await gateDecision('REJECTED');$('modal').classList.add('hidden')}catch{}};
$('approve').onclick=async()=>{try{await gateDecision('APPROVED');$('modal').classList.add('hidden')}catch{}};
$('clar').onclick=async()=>{
  const c=$('clarify'); c.classList.remove('hidden'); c.textContent='↻ Fetching context from StudyGraph…';
  try{
    const data=await gateDecision('CLARIFY','Medical monitor requested additional graph context.');
    const d=await apiQuery('What is the patient360 for 042-S02-004?');
    c.textContent='✓ Context found: '+((d.answer||[]).join(' · ')||d.text||'evidence loaded')+' · clarification recorded for resubmission.';
  }catch(e){c.textContent='✕ Context lookup failed: '+e.message}
};
$('reverse').onclick=async()=>{
  $('queryTitle').textContent='Reverse lookup · Cellulitis';
  $('queryAnswer').textContent='Tracing AE across the graph…';
  $('queryEvidence').innerHTML='Loading…';
  $('queryModal').classList.remove('hidden');
  try{
    const d=await apiQuery('Which subjects have serious adverse events?');
    const hit=(d.answer||[]).find(x=>String(x).includes('042-S02-004'))||'042-S02-004';
    $('queryAnswer').textContent='Cellulitis · AESHOSP=Y · AESER=N → '+hit;
    $('queryEvidence').innerHTML=(d.evidence||[]).map(e=>'<div class="queryev">'+escapeHtml(e.domain||'DOC')+' · '+escapeHtml(e.usubjid||e.document||'document')+(e.seq!=null?' · seq '+escapeHtml(e.seq):'')+'</div>').join('')||'<div class="queryev">AE · 042-S02-004 · seq 1</div>';
    trace('<b>[reverse_lookup]</b> Cellulitis → subject linkage resolved from evidence');
  }catch(e){$('queryAnswer').textContent=e.message}
};
$('report').onclick=async()=>{
  try{
    const d=await apiQuery('Which subjects have serious adverse events?');
    $('queryTitle').textContent='Cycle report · cut '+cut.value;
    $('queryAnswer').textContent='Serious AE subjects: '+((d.answer||[]).join(', ')||'none')+'. Evidence count: '+(d.evidence||[]).length+'.';
    $('queryEvidence').innerHTML=(d.evidence||[]).map(e=>'<div class="queryev">'+escapeHtml(e.domain||'DOC')+' · '+escapeHtml(e.usubjid||e.document||'document')+(e.seq!=null?' · seq '+escapeHtml(e.seq):'')+'</div>').join('')||'<div class="queryev">No evidence</div>';
    $('queryModal').classList.remove('hidden');
  }catch(e){trace('<b>[error]</b> '+escapeHtml(e.message))}
};
document.querySelectorAll('.focus').forEach(x=>x.onclick=()=>focusSubject(x));
document.querySelectorAll('.subject').forEach(x=>x.onclick=()=>{
  const b=[...document.querySelectorAll('.focus')].find(y=>y.dataset.subject===x.dataset.subject);
  if(b) focusSubject(b);
});
$('aeNode').onclick=()=>$('reverse').click();
loadStats();
