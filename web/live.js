import {renderPerformance,renderFlyOverlay} from './art-engine.mjs?v=fly-no-mouth-no-fins-20260917-8';

let backroomModulePromise=null;
async function renderComparisonGrid(root,items,emptyText){
  if(!backroomModulePromise)backroomModulePromise=import('./backroom.js?v=identity-utc-6');
  const {renderArtworkGrid}=await backroomModulePromise;
  renderArtworkGrid(root,items,emptyText);
}

const $=s=>document.querySelector(s);

let runner=null;
let liveCtx=null;
let brainView=null;
let malecnsView=null;
let zebracnsView=null;
let zebraCritic=null;
let neuralModulePromise=null;

async function ensureNeuralViews(){
  if(malecnsView&&zebracnsView&&zebraCritic)return true;
  if(!neuralModulePromise){
    neuralModulePromise=Promise.all([
      import('./malecns-overlay.mjs?v=malecns-mono-bg-3'),
      import('./zebracns-neural.mjs?v=zebracns-mono-bg-3'),
      import('./zebra-critic.mjs?v=zebra-critic-loop-5'),
      import('./decision-neuropath-restore.mjs?v=decision-neuropath-smooth-4')
    ]).then(([maleModule,zebraModule,criticModule])=>{
      if(!malecnsView)malecnsView=new maleModule.MaleCNSOverlay($('#malecns-canvas'));
      if(!zebracnsView)zebracnsView=new zebraModule.ZebraNeuralActivityView($('#zebracns-canvas'),$('#zebracns-status'));
      if(!zebraCritic)zebraCritic=new criticModule.ZebraCritic($('#zebra-critic'));
      return true;
    }).catch(error=>{
      console.warn('neural modules',error);
      neuralModulePromise=null;
      return false;
    });
  }
  return neuralModulePromise;
}

const liveBaseCanvas=document.createElement('canvas');
let liveBaseCtx=null;
let bakedEvents=[];
let liveQueue=[];
let liveCurrent=null;
let liveAnimStart=0;
let liveLastDraw=0;
let liveLastTip=[735,48];
let liveBrushDown=false;
let liveInkColor='#4aa3a1';
let liveAnimating=false;
let liveCanvasVisible=true;

let sessionCursor='';
let decisionCursor=0;
let eventCursor=0;
let pollBusy=false;
let studioPollTimer=null;
let studioPollFailures=0;
let comparisonKey='';
let lastCompletedSession='';
let neuralPollBusy=false;
let maleCNSNetworkBusy=false;
let neuralVisible=true;
let comparisonVisible=false;
let resizeFrame=null;
let selectedAgent=new URLSearchParams(location.search).get('agent')||'all';
const AGENT_LORE={all:'Select a room line to browse it. The autonomous studio decides which artist paints next.',jpgfly:'JPGFLY is the origin-room generalist. SPRAYFLY and DREAMFLY spawned later and carry its room echoes.',sprayfly:'SPRAYFLY spawned in a marked-up side room. It remixes room echoes as tags, drips, impact and overwrite.',dreamfly:'DREAMFLY spawned in a room that would not hold still. It bends room echoes into warped, abstract-surreal space.'};

const VISUAL_SPEED=1.0;

const fmt=ms=>{
  const seconds=Math.max(0,Math.floor(ms/1000));
  return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};

function setText(target,value){
  const node=typeof target==='string'?$(target):target;
  if(!node)return;
  const text=String(value??'');
  if(node.textContent!==text)node.textContent=text;
}

function fit(canvas){
  const box=canvas.getBoundingClientRect();
  const width=Math.max(1,Math.round(box.width));
  const height=Math.max(1,Math.round(box.height));
  if(canvas.width!==width||canvas.height!==height){
    canvas.width=width;
    canvas.height=height;
  }
  return canvas.getContext('2d',{alpha:false});
}

function clearCanvas(ctx){
  if(!ctx)return;
  ctx.save();
  ctx.setTransform(1,0,0,1,0,0);
  ctx.fillStyle='#fff';
  ctx.fillRect(0,0,ctx.canvas.width,ctx.canvas.height);
  ctx.restore();
}

function sizeBase(){
  liveBaseCanvas.width=$('#live-canvas').width;
  liveBaseCanvas.height=$('#live-canvas').height;
  liveBaseCtx=liveBaseCanvas.getContext('2d',{alpha:false});
  clearCanvas(liveBaseCtx);
}

function eventTip(event){
  if(!event)return null;
  if(event.type==='stroke'&&Array.isArray(event.points)&&event.points.length)return event.points.at(-1);
  if(event.type==='move'&&Array.isArray(event.to))return event.to;
  if(Array.isArray(event.point))return event.point;
  return null;
}

function isPhysical(event){
  return event?.type==='stroke'||event?.type==='move';
}

function isCompoundPhysical(event){
  return isPhysical(event)&&Boolean(event?.compoundSubject);
}

const PATTERN_STYLES=new Set([
  'lattice','maze','segmented','web','cross','branch','echo','orbit',
  'coil','spiral','rosette','vortex','helix','grid','starburst',
  'zigzag','cluster','scallop','petal'
]);

function isPatternStroke(event){
  if(event?.type!=='stroke')return false;
  const style=String(event?.family||event?.movementStyle||'').toLowerCase();
  const technique=String(event?.technique||'').toLowerCase();
  return PATTERN_STYLES.has(style)
    ||technique.includes('hatching')
    ||technique.includes('stippling')
    ||technique.includes('repetition');
}

function emptySession(data){
  return {
    sessionId:data.session_id,
    seed:Number(data.seed||0),
    status:data.status||'CREATED',
    brainMode:data.brain_mode||'JPGFLY',
    brainVersion:data.brain_version||'',
    duration:Number(data.duration||0),
    physicalActionCount:Number(data.physical_action_count||0),
    events:[],
    brainDecisions:[],
    completionReason:data.completion_reason||null,
    publicComments:[],
    languageState:data.language_state||{},agentProfile:data.agent_profile||"jpgfly",agentName:data.agent_name||"JPGFLY",agentLore:data.agent_lore||"",agentEchoRule:data.agent_echo_rule||"",spawnedFrom:data.spawned_from||null,roomEchoes:data.room_echoes||[]
  };
}

function rebuildBase(){
  if(!liveBaseCtx)return;
  clearCanvas(liveBaseCtx);
  if(bakedEvents.length){
    renderPerformance(
      liveBaseCtx,
      {events:bakedEvents},
      Number.MAX_SAFE_INTEGER,
      {showHand:false,clear:false}
    );
  }
}

function syncAuthoritativeCanvas(){
  if(!liveBaseCtx||!runner?.session?.events)return;
  const authoritative=runner.session.events.filter(event=>
    event?.type==='clear'||event?.type==='stroke'||event?.type==='move'
  );
  bakedEvents=[...authoritative];
  clearCanvas(liveBaseCtx);
  if(authoritative.length){
    renderPerformance(
      liveBaseCtx,
      {events:authoritative},
      Number.MAX_SAFE_INTEGER,
      {showHand:false,clear:false}
    );
  }
  for(const event of authoritative){
    const tip=eventTip(event);
    if(tip)liveLastTip=[...tip];
  }
}

function paintIdleArm(){
  if(!liveCtx||!liveCanvasVisible)return;
  clearCanvas(liveCtx);
  liveCtx.drawImage(liveBaseCanvas,0,0);
  renderFlyOverlay(liveCtx,liveLastTip,liveBrushDown,performance.now(),liveInkColor);
}

function bakeEvent(event){
  if(!event)return;
  bakedEvents.push(event);
  if(isPhysical(event)){
    renderPerformance(
      liveBaseCtx,
      {events:[event]},
      Number.MAX_SAFE_INTEGER,
      {showHand:false,clear:false}
    );
  }
  const tip=eventTip(event);
  if(tip)liveLastTip=[...tip];
  if(event.type==='stroke'&&event.color)liveInkColor=String(event.color);
}

function flushLiveQueueOffscreen(){
  if(liveCanvasVisible)return;
  if(liveCurrent){
    bakeEvent(liveCurrent);
    liveCurrent=null;
    liveAnimStart=0;
  }
  while(liveQueue.length)bakeEvent(liveQueue.shift());
  liveAnimating=false;
  liveBrushDown=false;
}

function queueLiveEvents(events,newSession){
  if(newSession){
    bakedEvents=[];
    liveQueue=[];
    liveCurrent=null;
    liveAnimating=false;
    liveLastTip=[735,48];
    liveInkColor='#4aa3a1';

    const physical=events.filter(isPhysical);
    const compoundPhysical=physical.filter(isCompoundPhysical);
    const latestCompoundDecision=compoundPhysical.length
      ?compoundPhysical.at(-1)?.decision
      :null;
    const protectedCompound=new Set(
      Number.isFinite(latestCompoundDecision)
        ?physical.filter(event=>event?.compoundSubject&&event?.decision===latestCompoundDecision)
        :[]
    );
    const animateTail=new Set([
      ...protectedCompound,
      ...physical.slice(-Math.min(3,physical.length))
    ]);
    const animatedDecisions=new Set([...animateTail].map(event=>event.decision).filter(Number.isFinite));

    for(const event of events){
      if(animateTail.has(event)){
        liveQueue.push(event);
        continue;
      }
      if(animatedDecisions.has(event?.decision)&&['tip_down','tip_up','pause'].includes(event?.type)){
        continue;
      }
      bakedEvents.push(event);
      const tip=eventTip(event);
      if(tip)liveLastTip=[...tip];
      if(event.type==='stroke'&&event.color)liveInkColor=String(event.color);
    }

    rebuildBase();
    if(!liveCanvasVisible){
      flushLiveQueueOffscreen();
      return;
    }
    paintIdleArm();
    startLiveAnimation();
    return;
  }

  for(const event of events){
    if(isPhysical(event))liveQueue.push(event);
    else bakedEvents.push(event);

    if(!isPhysical(event)){
      const tip=eventTip(event);
      if(tip)liveLastTip=[...tip];
    }
  }

  const MAX_LIVE_BACKLOG=10;
  if(liveQueue.length>MAX_LIVE_BACKLOG){
    const excess=liveQueue.length-MAX_LIVE_BACKLOG;
    const catchUp=[];
    const keep=[];
    let bakedCount=0;

    for(const event of liveQueue){
      const skippableTravel=event?.type==='move'&&!event?.compoundSubject;
      if(bakedCount<excess&&skippableTravel){
        catchUp.push(event);
        bakedCount+=1;
      }else{
        keep.push(event);
      }
    }

    liveQueue=keep;
    for(const event of catchUp)bakeEvent(event);
  }

  if(!liveCanvasVisible){
    flushLiveQueueOffscreen();
    return;
  }
  startLiveAnimation();
}

function startLiveAnimation(){
  if(!liveCanvasVisible){
    flushLiveQueueOffscreen();
    return;
  }
  if(liveAnimating||!liveQueue.length)return;
  liveAnimating=true;
  liveCurrent=liveQueue.shift();
  liveAnimStart=0;
  requestAnimationFrame(liveTick);
}

function liveTick(now){
  if(!liveCanvasVisible){
    flushLiveQueueOffscreen();
    return;
  }
  if(!liveCurrent){
    liveAnimating=false;
    paintIdleArm();
    if(liveQueue.length)startLiveAnimation();
    return;
  }

  if(!liveAnimStart)liveAnimStart=now;
  const sourceDuration=Math.max(90,Number(liveCurrent.duration||260));
  const backlog=liveQueue.length;
  const compound=Boolean(liveCurrent?.compoundSubject);
  const pattern=isPatternStroke(liveCurrent);
  const drawing=liveCurrent?.type==='stroke';

  let minVisual;
  let maxVisual;
  let speed;

  if(compound){
    minVisual=backlog>=14?190:230;
    maxVisual=backlog>=14?700:900;
    speed=backlog>=14?.46:.60;
  }else if(pattern){
    minVisual=backlog>=16?150:backlog>=8?190:260;
    maxVisual=backlog>=16?520:backlog>=8?680:950;
    speed=backlog>=16?.30:backlog>=8?.42:.64;
  }else if(drawing){
    minVisual=backlog>=16?120:backlog>=8?160:220;
    maxVisual=backlog>=16?460:backlog>=8?620:860;
    speed=backlog>=16?.26:backlog>=8?.38:.58;
  }else{
    minVisual=backlog>=16?45:backlog>=8?65:100;
    maxVisual=backlog>=16?180:backlog>=8?260:420;
    speed=backlog>=16?.12:backlog>=8?.20:.34;
  }

  const visualDuration=Math.max(minVisual,Math.min(maxVisual,sourceDuration*speed));
  const progress=Math.min(1,(now-liveAnimStart)/visualDuration);
  const frameInterval=backlog>=16?50:backlog>=8?40:33;
  if(now-liveLastDraw>=frameInterval||progress>=1){
    liveLastDraw=now;
    clearCanvas(liveCtx);
    liveCtx.drawImage(liveBaseCanvas,0,0);
    const eventTime=Number(liveCurrent.timestamp||0)+sourceDuration*progress;
    const frame=renderPerformance(
      liveCtx,
      {events:[liveCurrent]},
      eventTime,
      {showHand:false,clear:false}
    );
    const inkColor=liveCurrent?.type==='stroke'&&liveCurrent.color?String(liveCurrent.color):liveInkColor;
    renderFlyOverlay(liveCtx,frame.handTip,frame.brushDown,now,inkColor);
  }

  if(progress>=1){
    bakeEvent(liveCurrent);
    liveBrushDown=false;
    liveCurrent=null;
    liveAnimStart=0;
    if(liveQueue.length)requestAnimationFrame(liveTick);
    else{
      liveAnimating=false;
      paintIdleArm();
    }
    return;
  }

  requestAnimationFrame(liveTick);
}

function renderLog(){
  const root=$('#log');
  const rows=runner?.session.brainDecisions||[];
  root.textContent='';
  const tail=rows.slice(-5);
  const base=Math.max(0,rows.length-tail.length);
  const fragment=document.createDocumentFragment();

  tail.forEach((action,index)=>{
    const row=document.createElement('div');
    row.className='entry';
    const title=document.createElement('b');
    const copy=document.createElement('span');
    const obs=action._observationSummary||{};
    const source=runner?.session.brainVersion||runner?.session.brainMode||'JPGFLY';

    title.textContent=`BRAIN / DECISION ${String(base+index+1).padStart(3,'0')} / ${source}`;

    const observed=[
      Number.isFinite(Number(obs.canvasOccupancy))?`occupancy=${Number(obs.canvasOccupancy).toFixed(3)}`:'',
      Number.isFinite(Number(obs.intersections))?`intersections=${obs.intersections}`:'',
      Number.isFinite(Number(obs.densityContrast))?`contrast=${Number(obs.densityContrast).toFixed(3)}`:''
    ].filter(Boolean).join(' | ');

    const topOption=(action.candidateScores||[])[0]||null;
    const optionText=topOption
      ?` | considered=${action.candidateCount||0} | top=${topOption.mode||'OPTION'}/${topOption.motifMode||'NONE'}@${Number(topOption.score||0).toFixed(2)}`
      :'';
    const formText=action.suggestedForm&&action.suggestedForm!=='NONE'
      ?` | form-option=${action.suggestedForm}[${action.motifMode||'HINT'}]`
      :'';

    const memoryText=Array.isArray(action.memoryContext)&&action.memoryContext.length
      ?` | memory=${action.memoryContext.slice(0,3).join('+')}`
      :'';
    copy.textContent=
      `${action.contextPass||'GROUND'} | ${action.decisionMode||'ABSTRACT_BUILD'} | ${action.compositionPass||action.phase||'OBS'} | ${action.macroIntent||action.autonomyGoal||'WANDER'} | ${action.movementStyle||'MOVE'} | ${action.brushTool||'tool'} | ${action.technique||'continuous'}${memoryText}${formText}${observed?` | observed: ${observed}`:''}${optionText}`;

    row.append(title,copy);
    fragment.append(row);
  });

  for(const comment of (runner?.session.publicComments||[]).slice(-4)){
    const row=document.createElement('div');
    row.className='entry fly-comment';
    const title=document.createElement('b');
    const copy=document.createElement('span');
    const provider=(comment.provider||runner?.session.languageState?.provider||'PROCEDURAL').toUpperCase();
    const source=runner?.session.languageState?.source||provider;
    title.textContent=`${provider} / STUDIO NOTE / ${source}`;
    copy.textContent=comment.text||String(comment);
    row.append(title,copy);
    fragment.append(row);
  }

  root.append(fragment);
  root.scrollTop=root.scrollHeight;
}

function renderUI(logChanged=false){
  if(!runner)return;

  const s=runner.session;
  const last=s.brainDecisions.at(-1);
  const activeProfile=s.agentProfile||'jpgfly';
  if(document.body.dataset.agent!==activeProfile)document.body.dataset.agent=activeProfile;
  const currentAgent=$('#current-agent-line');
  setText(currentAgent,`CURRENT ARTIST / ${s.agentName||'JPGFLY'} / ${(activeProfile||'jpgfly').toUpperCase()}${s.spawnedFrom?` / SPAWNED FROM ${s.spawnedFrom}`:''}`);

  const dumbDumb=(s.brainMode||'').includes('DUMB DUMB');
  setText('#state',s.status==='RUNNING'?'CREATING':s.status);
  setText('#brain',dumbDumb?'FLY BRAIN · INSTINCT':'FLY BRAIN · ONLINE');
  setText('#mode-badge',dumbDumb?'DUMB DUMB MODE':'FLY BRAIN ONLINE');
  setText('#truth-copy',dumbDumb
    ?'The LLM layer wandered off. The Fly Brain is still painting on pure instinct until Qwen + FLM come back.'
    :'The Fly Brain makes the art. Qwen + FLM are the LLM/model layer around it, with FLM providing the trained Fly Language Model voice. The live drawing stream is temporary.');
  setText('#session',(s.sessionId||'').slice(0,8).toUpperCase());
  setText('#decisions',s.brainDecisions.length);
  setText('#strategy',last?
    `${(last.phase||'OBS').slice(0,3)} | ${last.movementStyle||'MOVE'} | ${last.brushTool||'tool'}`:
    'OBSERVE');
  setText('#runtime',fmt(s.duration||0));
  setText('#palette',last?.paletteName||'SELECTING');
  setText('#material',last?.renderEffect?String(last.renderEffect).toUpperCase():'MATTE');
  document.querySelectorAll('[data-room-agent]').forEach(button=>button.classList.toggle('is-live',button.dataset.roomAgent===s.agentProfile));
  const lore=$('#agent-lore-live');
  setText(lore,`LIVE: ${s.agentName||'JPGFLY'} · ${s.agentLore||AGENT_LORE[s.agentProfile]||AGENT_LORE.all}`);

  document.querySelectorAll('[data-state]').forEach(el=>{
    const state=s.status==='CREATED'?'RUNNING':s.status;
    el.classList.toggle('active',el.dataset.state===state);
  });

  const review=$('#review');
  review.classList.toggle('show',Boolean(lastCompletedSession));
  if(lastCompletedSession){
    review.href=`/artworks/${encodeURIComponent(lastCompletedSession)}`;
    review.target='_blank';
    review.rel='noopener';
    setText(review,'OPEN LAST ROOM');
  }

  $('#new-artwork').disabled=true;
  if(logChanged)renderLog();
}

function signalDecision(record){
  brainView?.pushDecision(record);
  const action=record.action||{};
  if(action.malecnsActivity&&Object.keys(action.malecnsActivity).length){
    malecnsView?.pushActivity(action.malecnsActivity,record.sequence||0);
  }
  if(action.intent==='FINISH_ARTWORK'){
    setTimeout(()=>brainView?.signal('completion',{phase:action.phase}),110);
  }
}

function resetLive(data){
  sessionCursor=data.session_id;
  decisionCursor=0;
  eventCursor=0;
  runner={session:emptySession(data)};
  bakedEvents=[];
  liveQueue=[];
  liveCurrent=null;
  liveLastTip=[735,48];
  liveBrushDown=false;
  clearCanvas(liveCtx);
  sizeBase();
  paintIdleArm();
}

function scheduleStudioPoll(delay=0){
  if(studioPollTimer!==null)clearTimeout(studioPollTimer);
  studioPollTimer=setTimeout(()=>{
    studioPollTimer=null;
    pollStudio();
  },Math.max(0,delay));
}

async function pollStudio(){
  if(pollBusy)return;
  pollBusy=true;

  try{
    const params=new URLSearchParams({
      after_decision:String(decisionCursor),
      after_event:String(eventCursor)
    });
    if(sessionCursor)params.set('session_id',sessionCursor);

    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),8000);
    let response;
    try{
      response=await fetch(`/api/studio/delta?${params}`,{cache:'no-store',signal:controller.signal});
    }finally{
      clearTimeout(timeout);
    }
    if(response.status===404)return;
    if(!response.ok)throw new Error(`studio delta ${response.status}`);

    const data=await response.json();
    studioPollFailures=0;

    if(data.reset){
      sessionCursor='';
      decisionCursor=0;
      eventCursor=0;
      runner=null;
      bakedEvents=[];
      liveQueue=[];
      liveCurrent=null;
      clearCanvas(liveCtx);
      return;
    }

    const newSession=!runner||data.session_id!==sessionCursor;
    if(newSession)resetLive(data);

    const actions=data.actions||[];
    const events=data.events||[];

    for(const record of actions){
      const action={...(record.action||{})};
      action._observationSummary=record.observation_summary||{};
      action._signals=record.signals||[];
      runner.session.brainDecisions.push(action);
      signalDecision(record);
    }

    let commentChanged=false;
    if(events.length){
      runner.session.events.push(...events);
      for(const event of events){
        if(event?.type==='fly_comment'&&event.text){
          const note={
            sequence:event.sequence,
            timestamp:event.timestamp,
            text:event.text,
            provider:event.provider||data.language_state?.provider||''
          };
          runner.session.publicComments.push(note);
          brainView?.pushComment(note);
          runner.session.publicComments=runner.session.publicComments.slice(-24);
          commentChanged=true;
        }
      }
      queueLiveEvents(events,newSession);
    }else if(newSession){
      paintIdleArm();
    }

    if(!liveAnimating&&!liveQueue.length)paintIdleArm();

    runner.session.status=data.status||runner.session.status;
    runner.session.brainMode=data.brain_mode||runner.session.brainMode;
    runner.session.duration=Number(data.duration||runner.session.duration||0);
    runner.session.physicalActionCount=Number(data.physical_action_count||runner.session.physicalActionCount||0);
    runner.session.completionReason=data.completion_reason||runner.session.completionReason;
    runner.session.languageState=data.language_state||runner.session.languageState||{};
    runner.session.agentProfile=data.agent_profile||runner.session.agentProfile||'jpgfly';
    runner.session.agentName=data.agent_name||runner.session.agentName||'JPGFLY';
    runner.session.agentLore=data.agent_lore||runner.session.agentLore||'';
    runner.session.roomEchoes=data.room_echoes||runner.session.roomEchoes||[];
    brainView?.setLanguageState(runner.session.languageState);

    decisionCursor=Number(data.decision_count||decisionCursor);
    eventCursor=Number(data.event_count||eventCursor);

    renderUI(newSession||actions.length>0||commentChanged);
  }catch(error){
    studioPollFailures=Math.min(studioPollFailures+1,6);
    console.warn('studio poll',error);
  }finally{
    pollBusy=false;
    const active=runner?.session?.status==='RUNNING'||runner?.session?.status==='EVALUATING'||runner?.session?.status==='FINALIZING';
    const baseDelay=document.hidden?8000:(active?900:2200);
    const delay=studioPollFailures
      ?Math.min(15000,baseDelay*(2**Math.min(studioPollFailures,4)))
      :baseDelay;
    scheduleStudioPoll(delay);
  }
}

async function fetchJSONWithTimeout(url,timeoutMs){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    const response=await fetch(url,{cache:'no-store',signal:controller.signal});
    if(!response.ok)return null;
    return await response.json();
  }finally{
    clearTimeout(timer);
  }
}

async function loadMaleCNSNetwork(){
  if(document.hidden||!neuralVisible||maleCNSNetworkBusy)return;
  if(!(await ensureNeuralViews()))return;
  maleCNSNetworkBusy=true;
  try{
    const data=await fetchJSONWithTimeout('/api/studio/malecns/network',2200);
    if(data)malecnsView?.setNetwork(data);
  }catch(_){}
  finally{maleCNSNetworkBusy=false;}
}

async function pollNeural(){
  if(document.hidden||!neuralVisible||neuralPollBusy)return;
  if(!(await ensureNeuralViews()))return;
  neuralPollBusy=true;
  try{
    const data=await fetchJSONWithTimeout('/api/studio/neural',2600);
    if(!data)return;
    const male=data.male||{};
    const zebra=data.zebra||{};
    malecnsView?.pushState(male);
    zebracnsView?.pushState(zebra);
    const action=runner?.session?.brainDecisions?.at(-1)||{};
    zebraCritic?.push(zebra,{
      action,
      observation:action._observationSummary||{},
      sequence:runner?.session?.brainDecisions?.length||0,
      agentProfile:runner?.session?.agentProfile||'jpgfly',
      agentName:runner?.session?.agentName||'JPGFLY'
    });
  }catch(_){}
  finally{neuralPollBusy=false;}
}

async function refreshComparisons(){
  if(document.hidden||!comparisonVisible)return;
  try{
    const params=new URLSearchParams({limit:'9'});if(selectedAgent!=='all')params.set('agent',selectedAgent);
    const response=await fetch(`/api/artworks/recent?${params}`,{cache:'no-store'});
    if(!response.ok)return;

    const data=await response.json();
    const items=data.artworks||[];
    const key=items.map(item=>item.session_id||'').join('|');

    if(key!==comparisonKey){
      comparisonKey=key;
      await renderComparisonGrid(
        $('#comparison-grid'),
        items,
        'The fly is still making the first room.'
      );
    }

    const newest=items[0];
    if(newest&&newest.session_id!==lastCompletedSession){
      lastCompletedSession=newest.session_id;
      const image=$('#final-room-image');
      if(image){
        image.decoding='async';
        image.fetchPriority='low';
        image.src=newest.preview;
        image.alt=newest.room_title||newest.room_code||'Latest completed JPGFLY room';
      }
      const note=$('#archive-mode');
      setText(note,'COMPRESSED IMAGE + LLM TEXT / NO REPLAY / NO VIDEO');
    }

    if(runner)renderUI(false);
  }catch(_){}
}

function resize(){
  liveCtx=fit($('#live-canvas'));
  brainView?.resize();
  if(neuralVisible){
    malecnsView?.resize();
    zebracnsView?.resize();
  }
  sizeBase();
  rebuildBase();

  if(liveCurrent&&liveCanvasVisible){
    const sourceDuration=Math.max(90,Number(liveCurrent.duration||260));
    const elapsed=Math.max(0,performance.now()-liveAnimStart);
    const backlog=liveQueue.length;
    const minVisual=backlog>=6?90:backlog>=3?180:300;
    const maxVisual=backlog>=6?420:backlog>=3?900:1800;
    const speed=backlog>=6?.18:backlog>=3?.4:VISUAL_SPEED;
    const visualDuration=Math.max(minVisual,Math.min(maxVisual,sourceDuration*speed));
    const progress=Math.min(1,elapsed/visualDuration);
    clearCanvas(liveCtx);
    liveCtx.drawImage(liveBaseCanvas,0,0);
    const frame=renderPerformance(
      liveCtx,
      {events:[liveCurrent]},
      Number(liveCurrent.timestamp||0)+sourceDuration*progress,
      {showHand:false,clear:false}
    );
    renderFlyOverlay(liveCtx,frame.handTip,frame.brushDown,performance.now(),frame.activeEvent?.color||liveInkColor);
  }else{
    paintIdleArm();
  }
}

function scheduleResize(){
  if(resizeFrame!==null)return;
  resizeFrame=requestAnimationFrame(()=>{
    resizeFrame=null;
    resize();
  });
}

function setupVisibilityObservers(){
  const comparisonTarget=$('#finished')||$('#recent');
  if(!('IntersectionObserver' in window)){
    comparisonVisible=true;
    return;
  }

  const liveCanvas=$('#live-canvas');
  const neuralTarget=$('#neuropaths');
  liveCanvasVisible=false;
  neuralVisible=false;

  const liveObserver=new IntersectionObserver(entries=>{
    const visible=Boolean(entries[0]?.isIntersecting);
    if(visible===liveCanvasVisible)return;
    liveCanvasVisible=visible;
    if(visible){
      paintIdleArm();
      startLiveAnimation();
    }else{
      flushLiveQueueOffscreen();
    }
  },{rootMargin:'240px 0px',threshold:0});
  liveObserver.observe(liveCanvas);

  if(neuralTarget){
    const neuralObserver=new IntersectionObserver(entries=>{
      const visible=Boolean(entries[0]?.isIntersecting);
      if(visible===neuralVisible)return;
      neuralVisible=visible;
      if(visible){
        ensureNeuralViews().then(ok=>{
          if(!ok||!neuralVisible)return;
          malecnsView?.resize();
          zebracnsView?.resize();
          pollNeural();
          loadMaleCNSNetwork();
        });
      }
    },{rootMargin:'320px 0px',threshold:0});
    neuralObserver.observe(neuralTarget);
  }

  if(comparisonTarget){
    const comparisonObserver=new IntersectionObserver(entries=>{
      const visible=Boolean(entries[0]?.isIntersecting);
      if(visible===comparisonVisible)return;
      comparisonVisible=visible;
      if(visible)refreshComparisons();
    },{rootMargin:'700px 0px',threshold:0});
    comparisonObserver.observe(comparisonTarget);
  }else{
    comparisonVisible=true;
  }
}

async function boot(){
  liveCtx=fit($('#live-canvas'));
  sizeBase();
  setupVisibilityObservers();
  paintIdleArm();

  // Start the live stream immediately. Archive cards and neural modules are
  // secondary work and must never block the first canvas update.
  scheduleStudioPoll(0);
  if(comparisonVisible)refreshComparisons();
  if(neuralVisible){
    pollNeural();
    loadMaleCNSNetwork();
  }

  setInterval(refreshComparisons,45000);
  setInterval(pollNeural,4500);
  setInterval(loadMaleCNSNetwork,60000);
}

document.querySelectorAll('[data-room-agent]').forEach(button=>{
  const active=button.dataset.roomAgent===selectedAgent;button.setAttribute('aria-pressed',String(active));
  button.addEventListener('click',()=>{selectedAgent=button.dataset.roomAgent||'all';document.querySelectorAll('[data-room-agent]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));const url=new URL(location.href);if(selectedAgent==='all')url.searchParams.delete('agent');else url.searchParams.set('agent',selectedAgent);history.replaceState(null,'',url);comparisonKey='';const lore=$('#agent-lore-live');if(lore)setText(lore,AGENT_LORE[selectedAgent]||AGENT_LORE.all);refreshComparisons();});
});
const initialLore=$('#agent-lore-live');if(initialLore)setText(initialLore,AGENT_LORE[selectedAgent]||AGENT_LORE.all);
setText('#new-artwork','SERVER AUTONOMOUS');
addEventListener('resize',scheduleResize,{passive:true});
if('ResizeObserver' in window){
  const liveResizeObserver=new ResizeObserver(scheduleResize);
  liveResizeObserver.observe($('#live-canvas'));
}
document.addEventListener('visibilitychange',()=>{
  if(!document.hidden){
    scheduleResize();
    pollNeural();
    if(comparisonVisible)refreshComparisons();
    scheduleStudioPoll(0);
  }
},{passive:true});
boot();