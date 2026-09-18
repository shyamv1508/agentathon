const $=id=>document.getElementById(id);
const q=$('question'),cut=$('cut'),ask=$('ask'),result=$('result'),loading=$('loading');

async function loadStats(){
  try{
    const r=await fetch('/api?stats=1');
    if(!r.ok) throw new Error('Stats request failed');
    const s=await r.json();
    $('subjects').textContent=s.subjects ?? '—';
    $('records').textContent=s.records ?? '—';
    $('nodes').textContent=s.nodes ?? '—';
    $('cuts').textContent='12';
  }catch(_){/* Keep the placeholders if the API is unavailable. */}
}

async function run(){
  const text=q.value.trim();
  if(!text)return q.focus();
  ask.disabled=true;loading.classList.remove('hidden');result.classList.add('hidden');
  try{
    const r=await fetch(`/api?q=${encodeURIComponent(text)}&cut=${cut.value}`);
    const data=await r.json();
    if(!r.ok)throw new Error(data.error||'Request failed');
    render(data);
  }catch(e){render({error:e.message})}
  finally{ask.disabled=false;loading.classList.add('hidden')}
}

function render(d){
  result.classList.remove('hidden');
  if(d.error){
    $('resultTitle').textContent='Query error';
    $('answer').innerHTML=`<span>${esc(d.error)}</span>`;
    $('text').textContent='';
    $('evidence').innerHTML='';
    return;
  }
  $('resultTitle').textContent=`Verified answer · cut ${cut.value}`;
  $('confidence').textContent=`Confidence ${(d.confidence*100).toFixed(0)}%`;
  $('answer').innerHTML=(d.answer||[]).length?d.answer.map(x=>`<span>${esc(x)}</span>`).join(''):'<span>No qualifying result</span>';
  $('text').textContent=d.text||'';
  $('evidenceCount').textContent=`${(d.evidence||[]).length} source record(s)`;
  $('evidence').innerHTML=(d.evidence||[]).map(e=>`<div class="ev"><b>${esc(e.domain||'DOC')}</b> · ${esc(e.usubjid||e.document||'document')}${e.seq!=null?` · seq ${esc(e.seq)}`:''}${e.section?` · ${esc(e.section)}`:''}</div>`).join('')||'<div class="ev">No evidence records</div>';
}

function esc(x){return String(x).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
ask.addEventListener('click',run);
q.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))run()});
document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{q.value=b.dataset.q;run()});
loadStats();
