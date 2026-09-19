const $=id=>document.getElementById(id);
const el=(id)=>document.getElementById(id);
const safeText=(id,v)=>{const x=el(id);if(x)x.textContent=v};
const safeHtml=(id,v)=>{const x=el(id);if(x)x.innerHTML=v};
const cut=el('cut');

function escapeHtml(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function protocolFor(v){return v>=9?'v3':v>=6?'v2':'v1'}
function trace(msg){const t=el('trace');if(!t)return;const p=document.createElement('p');p.innerHTML=msg;t.appendChild(p);t.scrollTop=t.scrollHeight}
async function apiFetch(url,options={}){const r=await fetch(url,options);const raw=await r.text();let d={};try{d=raw?JSON.parse(raw):{}}catch{throw new Error('API returned an invalid response ('+r.status+')')}if(!r.ok)throw new Error(d.detail||d.message||('API request failed ('+r.status+')'));return d}

async function loadCut(v){
 const s=await apiFetch('/api/stats?cut='+v);
 safeText('subjects',s.subjects??'—');safeText('records',s.records??'—');safeText('siteCount',(s.sites??12)+' sites');safeText('cutCount',(s.cuts??12)+' cuts indexed');safeText('protocol',protocolFor(v));safeText('protocolContext','Protocol '+protocolFor(v));safeText('critical',s.critical??'—');safeText('pending',s.pending??'—');
 trace('<b>[system]</b> Data cut '+v+' loaded · '+(s.records??0)+' visible records · protocol '+protocolFor(v));
}
async function apiQuery(q){return apiFetch('/api/query?q='+encodeURIComponent(q)+'&cut='+(cut?.value||12))}
function openModal(id){const x=el(id);if(x)x.classList.remove('hidden')}
function closeModal(id){const x=el(id);if(x)x.classList.add('hidden')}

async function runCycle(){
 const b=el('cycle');if(b)b.disabled=true;safeText('termstatus','RUNNING');trace('<b>[system]</b> Starting live MONITOR cycle…');
 try{const d=await apiFetch('/api/cycle?cut='+(cut?.value||12));safeText('pending',d.stats?.pending_escalations??d.pending_escalations?.length??0);safeText('critical',d.stats?.escalations??0);safeText('footerStatus',(d.stats?.findings??0)+' findings · '+(d.stats?.escalations??0)+' escalations · cut '+(cut?.value||12));trace('<b>[execute]</b> '+(d.stats?.findings??0)+' findings · '+(d.stats?.escalations??0)+' escalations');}catch(e){trace('<b>[error]</b> '+escapeHtml(e.message))}finally{if(b)b.disabled=false;safeText('termstatus','IDLE')}
}

async function gateDecision(decision,reason=''){
 const c=+(cut?.value||12);
 const d=await apiFetch('/api/gate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cut:c,code:'SAE_MISCODED',usubjid:'042-S02-004',decision,reason})});
 trace('<b>[human_gate]</b> '+decision+' SAE_MISCODED → '+(d.escalation?.status||decision.toLowerCase()));return d
}

function bind(){
 const b=id=>el(id);
 b('cycle')?.addEventListener('click',runCycle);
 b('gate')?.addEventListener('click',()=>openModal('modal'));
 b('bell')?.addEventListener('click',()=>openModal('modal'));
 b('close')?.addEventListener('click',()=>closeModal('modal'));
 b('queryClose')?.addEventListener('click',()=>closeModal('queryModal'));
 b('cut')?.addEventListener('change',()=>{try{loadCut(+(cut.value||12))}catch(e){trace('<b>[error]</b>'+escapeHtml(e.message))}});
 b('reject')?.addEventListener('click',async()=>{try{await gateDecision('REJECTED');closeModal('modal')}catch(e){trace('<b>[error]</b>'+escapeHtml(e.message))}});
 b('approve')?.addEventListener('click',async()=>{try{await gateDecision('APPROVED');closeModal('modal')}catch(e){trace('<b>[error]</b>'+escapeHtml(e.message))}});
 b('clar')?.addEventListener('click',async()=>{const x=b('clarify');if(x){x.classList.remove('hidden');x.textContent='↻ Fetching context from StudyGraph…'}try{await gateDecision('CLARIFY','Medical monitor requested additional graph context.');const d=await apiQuery('What is the patient360 for 042-S02-004?');if(x)x.textContent='✓ Context found: '+(d.text||'evidence loaded')}catch(e){if(x)x.textContent='✕ '+e.message}});
 b('report')?.addEventListener('click',async()=>{try{const d=await apiQuery('Which subjects have serious adverse events?');openModal('queryModal');safeText('queryTitle','Cycle report · cut '+(cut?.value||12));safeText('queryAnswer','Serious AE subjects: '+((d.answer||[]).join(', ')||'none'));safeHtml('queryEvidence',(d.evidence||[]).map(e=>'<div class="queryev">'+escapeHtml(e.domain||'DOC')+' · '+escapeHtml(e.usubjid||e.document||'document')+(e.seq!=null?' · seq '+escapeHtml(e.seq):'')+'</div>').join('')||'<div class="queryev">No evidence</div>')}catch(e){trace('<b>[error]</b>'+escapeHtml(e.message))}});
 b('reverse')?.addEventListener('click',async()=>{openModal('queryModal');safeText('queryTitle','Reverse lookup · Cellulitis');try{const d=await apiQuery('Which subjects have serious adverse events?');safeText('queryAnswer','Cellulitis · AESHOSP=Y · AESER=N → '+((d.answer||[]).find(x=>String(x).includes('042-S02-004'))||'042-S02-004'))}catch(e){safeText('queryAnswer',e.message)}});
 b('aeNode')?.addEventListener('click',()=>b('reverse')?.click());
 document.querySelectorAll('.focus').forEach(x=>x.addEventListener('click',()=>{}));
}
function start(){bind();if(cut)loadCut(+(cut.value||12)).catch(e=>trace('<b>[error]</b>'+escapeHtml(e.message)))}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
