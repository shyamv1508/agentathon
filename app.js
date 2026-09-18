const $=id=>document.getElementById(id), q=$('question'),cut=$('cut');
const traces=['[detect] Scanning active subjects and contradictions…','[medical_review] Reviewing clinical plausibility and baseline context…','[data_manager] Deduplicating record-cited queries…','[compliance] Applying protocol amendment delta…','[human_gate] Escalations ready for medical monitor…','[execute] Cycle state persisted for next cut.'];
function trace(msg){const t=$('trace');const p=document.createElement('p');p.textContent=msg;t.appendChild(p);t.scrollTop=t.scrollHeight}
$('cycle').onclick=async()=>{for(let i=0;i<6;i++){document.querySelectorAll('.node').forEach((n,j)=>n.classList.toggle('on',j===i));document.querySelectorAll('.node span')[i].textContent='ACTIVE';trace(traces[i]);await new Promise(r=>setTimeout(r,260))}document.querySelectorAll('.node span').forEach(x=>x.textContent='READY');$('p5').querySelector('span').textContent='COMPLETE';};
cut.onchange=()=>{const v=+cut.value;$('protocol').textContent=v>=9?'v3':v>=6?'v2':'v1';trace('[system] Data cut '+v+' loaded · protocol '+$('protocol').textContent)};
$('bell').onclick=$('gate').onclick=()=>{$('modal').classList.remove('hidden')};
$('close').onclick=()=>{$('modal').classList.add('hidden')};
$('reject').onclick=()=>{trace('[human_gate] REJECTED SAE_MISCODED → monitoring only');$('pending').textContent='5';$('modal').classList.add('hidden')};
$('approve').onclick=()=>{trace('[human_gate] APPROVED SAE_MISCODED → execute');$('pending').textContent='5';$('modal').classList.add('hidden')};
$('clar').onclick=()=>{const c=$('clarify');c.classList.remove('hidden');c.textContent='↻ Fetching context from StudyGraph…';setTimeout(()=>{c.textContent='✓ Context found: screening ALT 239.7 U/L · CM reviewed · clarification ready for resubmission.';trace('[human_gate] CLARIFY → baseline context appended → resubmitted')},700)};
$('reverse').onclick=()=>{trace('[reverse_lookup] Cellulitis · AESHOSP=Y → linked subjects: 042-S02-004');alert('Cellulitis reverse lookup\n\n042-S02-004 · AE seq 1\nAESHOSP=Y · AESER=N\nResult: SAE_MISCODED')};
$('report').onclick=()=>alert('ATLAS CYCLE REPORT\n\nFindings: 49\nEscalations: 8\nQueries: 0\nDeviations: 37\nProtocol: '+$('protocol').textContent+'\nCut: '+cut.value);
document.querySelectorAll('.subject').forEach(x=>x.onclick=()=>{trace('[patient360] Focused '+x.textContent);$('patient').textContent=x.textContent});
