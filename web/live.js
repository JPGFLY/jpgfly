import {renderPerformance,renderFlyOverlay} from './art-engine.mjs?v=brush-body-7';
import {renderArtworkGrid} from './backroom.js?v=identity-utc-6';
import {BrainActivityView} from './attribution-graph.mjs?v=attribution-1';
import {MaleCNSOverlay} from './malecns-overlay.mjs?v=malecns-live-3';

const $=s=>document.querySelector(s);

let runner=null;
let liveCtx=null;
let brainView=null;
let malecnsView=null;

const liveBaseCanvas=document.createElement('canvas');
let liveBaseCtx=null;
let bakedEvents=[];
let liveQueue=[];
let liveCurrent=null;
let liveAnimStart=0;
let liveLastDraw=0;
let liveLastTip=[735,48];
let liveBrushDown=false;
let liveAnimating=false;

let sessionCursor='';
let decisionCursor=0;
let eventCursor=0;
let pollBusy=false;
let comparisonKey='';
let lastCompletedSession='';

const VISUAL_SPEED=1.0;

const fmt=ms=>{
  const seconds=Math.max(0,Math.floor(ms/1000));
  return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};

function fit(canvas){
  const box=canvas.getBoundingClientRect();
  canvas.width=Math.max(1,Math.round(box.width));
  canvas.height=Math.max(1,Math.round(box.height));
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
    languageState:data.language_state||{}
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
  if(!liveCtx)return;
  clearCanvas(liveCtx);
  liveCtx.drawImage(liveBaseCanvas,0,0);
  renderFlyOverlay(liveCtx,liveLastTip,liveBrushDown,performance.now());
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
}

function queueLiveEvents(events,newSession){
  if(newSession){
    bakedEvents=[];
    liveQueue=[];
    liveCurrent=null;
    liveAnimating=false;
    liveLastTip=[735,48];

    // On reconnect, bake old history but animate the newest physical actions.
    // Never paint a complete incoming stroke before the fly has travelled it.
    const physical=events.filter(isPhysical);
    const animateTail=new Set(physical.slice(-Math.min(3,physical.length)));
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
    }

    rebuildBase();
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

  // Stay near live time. The Fly Brain can generate physical actions much
  // faster than the browser should replay them. Bake older backlog and keep
  // only the newest few movements for visible animation.
  const MAX_LIVE_BACKLOG=8;
  if(liveQueue.length>MAX_LIVE_BACKLOG){
    const catchUp=liveQueue.splice(0,liveQueue.length-MAX_LIVE_BACKLOG);
    for(const event of catchUp)bakeEvent(event);
  }

  startLiveAnimation();
}

function startLiveAnimation(){
  if(liveAnimating||!liveQueue.length)return;
  liveAnimating=true;
  liveCurrent=liveQueue.shift();
  liveAnimStart=0;
  requestAnimationFrame(liveTick);
}

function liveTick(now){
  if(!liveCurrent){
    liveAnimating=false;
    paintIdleArm();
    if(liveQueue.length)startLiveAnimation();
    return;
  }

  if(!liveAnimStart)liveAnimStart=now;
  const sourceDuration=Math.max(90,Number(liveCurrent.duration||260));
  const backlog=liveQueue.length;
  const minVisual=backlog>=6?90:backlog>=3?180:300;
  const maxVisual=backlog>=6?420:backlog>=3?900:1800;
  const speed=backlog>=6?.18:backlog>=3?.4:VISUAL_SPEED;
  const visualDuration=Math.max(minVisual,Math.min(maxVisual,sourceDuration*speed));
  const progress=Math.min(1,(now-liveAnimStart)/visualDuration);

  if(now-liveLastDraw>=32||progress>=1){
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
    renderFlyOverlay(liveCtx,frame.handTip,frame.brushDown,now);
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
  const tail=rows.slice(-8);
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

  for(const comment of (runner?.session.publicComments||[]).slice(-8)){
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

  const dumbDumb=(s.brainMode||'').includes('DUMB DUMB');
  $('#state').textContent=s.status==='RUNNING'?'CREATING':s.status;
  $('#brain').textContent=dumbDumb?'FLY BRAIN · INSTINCT':'FLY BRAIN · ONLINE';
  $('#mode-badge').textContent=dumbDumb?'DUMB DUMB MODE':'FLY BRAIN ONLINE';
  $('#truth-copy').textContent=dumbDumb
    ?'The LLM layer wandered off. The Fly Brain is still painting on pure instinct until Qwen + FLM come back.'
    :'The Fly Brain makes the art. Qwen + FLM are the LLM/model layer around it, with FLM providing the trained Fly Language Model voice. The live drawing stream is temporary.';
  $('#session').textContent=(s.sessionId||'').slice(0,8).toUpperCase();
  $('#decisions').textContent=s.brainDecisions.length;
  $('#strategy').textContent=last?
    `${(last.phase||'OBS').slice(0,3)} | ${last.movementStyle||'MOVE'} | ${last.brushTool||'tool'}`:
    'OBSERVE';
  $('#runtime').textContent=fmt(s.duration||0);

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
    review.textContent='OPEN LAST ROOM';
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

async function pollStudio(){
  if(pollBusy)return;
  pollBusy=true;

  try{
    const params=new URLSearchParams({
      after_decision:String(decisionCursor),
      after_event:String(eventCursor)
    });
    if(sessionCursor)params.set('session_id',sessionCursor);

    const response=await fetch(`/api/studio/delta?${params}`,{cache:'no-store'});
    if(response.status===404)return;
    if(!response.ok)throw new Error(`studio delta ${response.status}`);

    const data=await response.json();

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

    // The server stream remains authoritative, but active strokes stay queued
    // until the fly visibly travels them. Rebuilding from the complete stream
    // here would reveal the line before the fly reaches it.
    if(!liveAnimating&&!liveQueue.length)paintIdleArm();

    runner.session.status=data.status||runner.session.status;
    runner.session.brainMode=data.brain_mode||runner.session.brainMode;
    runner.session.duration=Number(data.duration||runner.session.duration||0);
    runner.session.physicalActionCount=Number(data.physical_action_count||runner.session.physicalActionCount||0);
    runner.session.completionReason=data.completion_reason||runner.session.completionReason;
    runner.session.languageState=data.language_state||runner.session.languageState||{};
    brainView?.setLanguageState(runner.session.languageState);

    decisionCursor=Number(data.decision_count||decisionCursor);
    eventCursor=Number(data.event_count||eventCursor);

    renderUI(newSession||actions.length>0||commentChanged);
  }catch(error){
    console.warn('studio poll',error);
  }finally{
    pollBusy=false;
    setTimeout(pollStudio,500);
  }
}

async function loadMaleCNSNetwork(){
  try{
    const response=await fetch('/api/studio/malecns/network',{cache:'no-store'});
    if(!response.ok)return;
    const data=await response.json();
    malecnsView?.setNetwork(data);
  }catch(_){}
}

async function pollMaleCNS(){
  try{
    const response=await fetch('/api/studio/malecns',{cache:'no-store'});
    if(!response.ok)return;
    const state=await response.json();
    malecnsView?.pushState(state);
  }catch(_){}
}

async function refreshComparisons(){
  try{
    const response=await fetch('/api/artworks/recent?limit=9',{cache:'no-store'});
    if(!response.ok)return;

    const data=await response.json();
    const items=data.artworks||[];
    const key=items.map(item=>item.session_id||'').join('|');

    if(key!==comparisonKey){
      comparisonKey=key;
      renderArtworkGrid(
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
        image.src=newest.preview;
        image.alt=newest.room_title||newest.room_code||'Latest completed JPGFLY room';
      }
      const note=$('#archive-mode');
      if(note)note.textContent='COMPRESSED IMAGE + LLM TEXT / NO REPLAY / NO VIDEO';
    }

    if(runner)renderUI(false);
  }catch(_){}
}

function resize(){
  liveCtx=fit($('#live-canvas'));
  brainView?.resize();
  malecnsView?.resize();
  sizeBase();
  rebuildBase();

  if(liveCurrent){
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
    renderFlyOverlay(liveCtx,frame.handTip,frame.brushDown,performance.now());
  }else{
    paintIdleArm();
  }
}

async function boot(){
  liveCtx=fit($('#live-canvas'));
  sizeBase();
  brainView=new BrainActivityView($('#brain-canvas'),$('#brain-status'));
  malecnsView=new MaleCNSOverlay($('#malecns-canvas'));
  paintIdleArm();
  await Promise.all([refreshComparisons(),loadMaleCNSNetwork(),pollMaleCNS()]);
  pollStudio();
  setInterval(refreshComparisons,12000);
  setInterval(pollMaleCNS,800);
  setInterval(loadMaleCNSNetwork,2500);
}

$('#new-artwork').textContent='SERVER AUTONOMOUS';
addEventListener('resize',resize,{passive:true});
boot();
