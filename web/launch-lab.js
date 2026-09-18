const $=s=>document.querySelector(s);
let state=null;
let tracking=false;
let animatingSession=null;
let inputSending=false;

function shortHash(value){
  if(!value)return '-';
  const s=String(value);
  return s.length>28 ? s.slice(0,16)+'…'+s.slice(-10) : s;
}

async function post(path,body={}){
  const r=await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  const data=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(data.detail||data.error||('HTTP '+r.status));
  return data;
}

function renderEvents(events){
  const root=$('#events');
  root.textContent='';
  if(!events?.length){
    const e=document.createElement('div');e.className='event muted';e.textContent='Waiting for ARM.';root.append(e);return;
  }
  const frag=document.createDocumentFragment();
  for(const item of [...events].reverse()){
    const row=document.createElement('div');row.className='event';
    const title=document.createElement('b');title.textContent=String(item.event||'EVENT');
    const copy=document.createElement('span');
    const bits=[];
    if(item.data?.decision)bits.push('decision='+item.data.decision);
    if(item.data?.reason)bits.push(item.data.reason);
    if(item.data?.result)bits.push('result='+item.data.result);
    bits.push(String(item.timestamp||''));
    copy.textContent=bits.join(' | ');
    row.append(title,copy);frag.append(row);
  }
  root.append(frag);
}

function moveFlyToLaunch(){
  const arena=$('#arena');
  const target=$('#launch-control');
  const fly=$('#fly-shell');
  const a=arena.getBoundingClientRect();
  const b=target.getBoundingClientRect();
  const x=b.left-a.left+b.width*.34;
  const y=b.top-a.top+b.height*.32;
  fly.style.left=x+'px';
  fly.style.top=y+'px';
  fly.style.transform='translate(-50%,-50%) rotate(8deg)';
}

function resetFly(){
  const fly=$('#fly-shell');
  fly.style.left='50%';
  fly.style.top='43%';
  fly.style.transform='translate(-50%,-50%)';
  $('#launch-control').classList.remove('agent-press','confirmed');
}

function animateAgentDecision(current){
  if(animatingSession===current.session_id)return;
  animatingSession=current.session_id;
  moveFlyToLaunch();
  setTimeout(()=>$('#launch-control').classList.add('agent-press'),1550);
  setTimeout(()=>$('#launch-control').classList.remove('agent-press'),2050);
}

function render(s){
  state=s;
  document.body.dataset.state=s.state||'IDLE';
  $('#state').textContent=s.state||'IDLE';
  $('#stack').textContent=s.stack?.healthy?'HEALTHY':'WAITING';
  $('#human-input').textContent=String(s.human_inputs_after_arm||0);
  $('#agent-actions').textContent=String(s.agent_actions||0);
  const readiness=s.readiness||{};
  $('#readiness').textContent=readiness.ready?'READY':'WAITING';
  const art=readiness.observed?.art_policy||{};
  $('#art-policy-status').textContent=Number.isFinite(Number(art.rooms_trained))
    ? String(art.rooms_trained)+' ROOMS / '+String(Math.round(Number(art.confidence||0)*100))+'%'
    : '-';
  const baseline=s.system_input_baseline||{};
  const finalInput=s.system_input_final||{};
  const hasSentinel=baseline.supported===true;
  const inputUnchanged=hasSentinel&&baseline.last_input_tick_ms===finalInput.last_input_tick_ms;
  $('#os-input-status').textContent=!hasSentinel?'WAITING':inputUnchanged?'UNCHANGED':'CHANGED';
  $('#build-status').textContent=s.build_manifest_hash?'SEALED':'WAITING';
  $('#session').textContent=s.session_id||'-';
  $('#policy-hash').textContent=shortHash(s.proof?.policy_hash);
  $('#intent-hash').textContent=shortHash(s.intent_hash);
  $('#receipt-hash').textContent=shortHash(s.receipt_hash||s.last_event_hash);
  renderEvents(s.events||[]);

  tracking=['ARMED','DECIDED'].includes(s.state);
  $('#arm').disabled=['ARMED','DECIDED'].includes(s.state);
  $('#reset').disabled=s.state==='IDLE';
  $('#proof-link').hidden=s.state!=='CONFIRMED';

  if(s.state==='DECIDED')animateAgentDecision(s);
  if(s.state==='CONFIRMED'){
    $('#launch-control').classList.add('confirmed');
    tracking=false;
  }
  if(s.state==='IDLE'){
    animatingSession=null;
    resetFly();
  }
}

async function poll(){
  try{
    const r=await fetch('/api/launch-lab/status',{cache:'no-store'});
    if(r.ok)render(await r.json());
  }catch(err){console.error(err)}
}

async function reportHumanInput(kind){
  if(!tracking||inputSending)return;
  inputSending=true;
  try{render(await post('/api/launch-lab/human-input',{kind}))}
  catch(err){console.error(err)}
  finally{inputSending=false}
}

$('#arm').addEventListener('click',async()=>{
  tracking=false;
  animatingSession=null;
  resetFly();
  try{render(await post('/api/launch-lab/arm'))}
  catch(err){alert(err.message)}
});

$('#reset').addEventListener('click',async()=>{
  tracking=false;
  try{render(await post('/api/launch-lab/reset'))}
  catch(err){alert(err.message)}
});

window.addEventListener('pointerdown',e=>{
  if(e.target.closest('#arm,#reset'))return;
  reportHumanInput('pointerdown');
},{capture:true});
window.addEventListener('keydown',()=>reportHumanInput('keydown'),{capture:true});
window.addEventListener('touchstart',e=>{
  if(e.target.closest('#arm,#reset'))return;
  reportHumanInput('touchstart');
},{capture:true,passive:true});

poll();
setInterval(poll,500);
