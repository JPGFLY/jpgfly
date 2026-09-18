const $=s=>document.querySelector(s);
const yes=(selector,value)=>{const el=$(selector);el.textContent=value?'YES':'NO';el.className=value?'yes':'no'};

function valueOrDash(value){return value==null||value===''?'-':String(value)}

async function load(){
  let verify,receipt;
  try{
    const [v,r]=await Promise.all([
      fetch('/api/launch-lab/verify',{cache:'no-store'}),
      fetch('/api/launch-lab/receipt',{cache:'no-store'})
    ]);
    verify=await v.json();
    receipt=await r.json();
    if(!v.ok)throw new Error(verify.detail||'verify failed');
    if(!r.ok)throw new Error(receipt.detail||'receipt unavailable');
  }catch(err){
    document.body.className='fail';
    $('#verdict').textContent='NO RECEIPT';
    $('#summary').textContent=err.message;
    return;
  }

  document.body.className=verify.verified?'pass':'fail';
  $('#verdict').textContent=verify.verified?'PROOF PASS':'PROOF FAIL';
  $('#summary').textContent=verify.verified
    ?'Audit chain, OS no-input marker, event order, and one-shot confirmation verified.'
    :'One or more proof invariants failed.';

  const events=receipt.events||[];
  const names=events.map(e=>e.event);
  yes('#human',!verify.human_input_after_arm&&!names.includes('SYSTEM_HUMAN_INPUT_DETECTED'));
  yes('#os-input',receipt.system_input_guard?.unchanged===true);
  const manifest=receipt.build_manifest||verify.build_manifest||{};
  yes('#git-clean',manifest.git_tracked_worktree_clean===true&&Boolean(manifest.git_commit));
  yes('#decision',names.includes('AGENT_DECISION'));
  yes('#activation',names.includes('AGENT_LAUNCH_CONTROL_ACTIVATED'));
  yes('#once',verify.confirmed_once);

  $('#session').textContent=valueOrDash(receipt.session_id);
  $('#commit').textContent=valueOrDash(manifest.git_commit);
  $('#manifest').textContent=valueOrDash(receipt.build_manifest_hash||verify.build_manifest_hash);
  $('#policy').textContent=valueOrDash(receipt.policy_hash);
  $('#art-policy').textContent=valueOrDash(manifest.art_policy_hash);
  $('#final-hash').textContent=valueOrDash(receipt.receipt_hash||verify.last_event_hash);
  $('#event-count').textContent=String(verify.event_count||0)+' EVENTS';

  const list=$('#event-list');list.textContent='';
  for(const event of events){
    const row=document.createElement('div');row.className='event';
    const title=document.createElement('b');title.textContent=String(event.sequence).padStart(2,'0')+' / '+event.event;
    const hash=document.createElement('code');hash.textContent=event.hash||'';
    row.append(title,hash);list.append(row);
  }

  if(verify.errors?.length){
    $('#errors').hidden=false;
    const ul=$('#error-list');ul.textContent='';
    for(const error of verify.errors){const li=document.createElement('li');li.textContent=error;ul.append(li)}
  }
}
load();
