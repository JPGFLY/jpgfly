import {CanvasMechanics} from './composition-engine.mjs?v=session-genome-4';
import {validateBrainAction} from './flybrain.mjs?v=motif-hints-3';

const WIDTH=800,HEIGHT=500;
const TAU=Math.PI*2;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const mix=(a,b,t)=>a+(b-a)*t;
const ease=t=>t*t*(3-2*t);
const distance=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
const clone=value=>JSON.parse(JSON.stringify(value));

function apiToSession(raw){
  return {sessionId:String(raw.session_id),seed:Number(raw.seed)>>>0,date:new Date().toISOString().slice(0,10),status:raw.status,brainMode:raw.brain_mode,
    parameters:raw.parameters||{},limits:raw.limits||{},duration:Number(raw.duration||0),decisionCount:Number(raw.decision_count||0),physicalActionCount:Number(raw.physical_action_count||0),
    events:raw.events||[],observations:[],brainDecisions:[],evaluationCheckpoints:raw.evaluation_checkpoints||[],publicLogs:[],completionReason:raw.completion_reason||null,
    provenance:raw.provenance||null,markFamilies:[],description:raw.metadata?.description||'The fly is observing the canvas.'};
}

function hashSource(value){const source=JSON.stringify(value);let hash=2166136261;for(let i=0;i<source.length;i++){hash^=source.charCodeAt(i);hash=Math.imul(hash,16777619)}return(hash>>>0).toString(16).padStart(8,'0')}
function formatClock(ms){const s=Math.floor(ms/1000);return`00:${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}

export class BackendFlyPerformance{
  constructor(apiSession,{localMechanics=false}={}){
    this.api=apiSession;this.session=apiToSession(apiSession);this.finished=apiSession.status==='COMPLETED';this.onBrainSignal=null;this.localMechanics=localMechanics;
    if(this.finished){this.session.events=clone(apiSession.events||[]);this.session.brainDecisions=(apiSession.brain_decisions||[]).map(item=>clone(item.action));this.session.observations=(apiSession.brain_decisions||[]).map(item=>clone(item.observation));return}
    this.session.events=clone(apiSession.events?.length?apiSession.events:[{type:'session_start',sessionId:this.session.sessionId,timestamp:0},{type:'clear',timestamp:20}]);
    this.mechanics=new CanvasMechanics(this.session.seed,this.session.events);
    if(localMechanics){for(const record of apiSession.brain_decisions||[])this.applyAction(record.action,record.observation,true)}
    else{this.session.brainDecisions=(apiSession.brain_decisions||[]).map(item=>clone(item.action));this.session.observations=(apiSession.brain_decisions||[]).map(item=>clone(item.observation));this.syncServerMechanics()}
  }
  syncServerMechanics(){
    if(!this.mechanics)return;
    let position=[735,48],clock=100,count=0;
    for(const event of this.session.events){
      if(event.type==='stroke'){position=[...event.points.at(-1)];clock=Math.max(clock,Number(event.timestamp||0)+Number(event.duration||0));count+=1}
      else if(event.type==='move'){position=[...event.to];clock=Math.max(clock,Number(event.timestamp||0)+Number(event.duration||0));count+=1}
      else if(event.type==='pause')clock=Math.max(clock,Number(event.timestamp||0)+Number(event.duration||0));
      else if(event.point)position=[...event.point];
    }
    this.mechanics.position=position;this.mechanics.clock=clock;this.mechanics.physicalActionCount=count;this.session.physicalActionCount=count;this.session.duration=Math.max(this.session.duration||0,clock);
  }
  applyServerDecision(result){
    const action=clone(result.action);if(!validateBrainAction(action))throw new Error('The server fly brain returned an invalid action');
    const observation=clone(result.observation||{}),sequence=this.session.brainDecisions.length;
    this.session.observations.push(observation);this.session.brainDecisions.push(action);this.session.decisionCount=this.session.brainDecisions.length;
    if(action.evaluation)this.session.evaluationCheckpoints.push(clone(action.evaluation));
    for(const event of result.events||[])this.session.events.push(clone(event));
    this.session.status=result.state;this.session.brainMode=result.brainMode;
    if(action.intent==='FINISH_ARTWORK')this.session.completionReason=action.reason;
    if(Number.isFinite(Number(result.serverClock)))this.session.duration=Number(result.serverClock);
    this.syncServerMechanics();
    if(action.intent==='FINISH_ARTWORK'){this.brainSignal('completion',{decision:sequence,phase:action.phase});this.session.publicLogs.push({timestamp:formatClock(this.session.duration),category:'STATE',message:'EVALUATING - the fly lifted her foreleg and ended the drawing.'});return false}
    this.brainSignal('action',{decision:sequence,movementStyle:action.movementStyle});
    this.session.publicLogs.push({timestamp:formatClock(this.session.duration),category:'ACTION',message:`${action.phase}: ${action.movementStyle} | ${action.brushTool} | ${action.technique}. ${action.reason}`});return true;
  }
  observation(){return this.mechanics.memory.observe(this.mechanics.position,this.mechanics.clock,this.session.brainDecisions.length,this.mechanics.physicalActionCount)}
  brainSignal(cluster,payload={},notify=true){this.session.events.push({type:'brain_signal',timestamp:this.mechanics?.clock||this.session.duration||0,cluster,...clone(payload)});if(notify&&this.onBrainSignal)this.onBrainSignal(cluster,payload)}
  applyAction(rawAction,recordedObservation=null,resuming=false){
    const action=clone(rawAction);if(!validateBrainAction(action))throw new Error('The server fly brain returned an invalid action');
    const observation=recordedObservation?clone(recordedObservation):this.observation();const sequence=this.session.brainDecisions.length;
    this.session.observations.push(observation);this.session.brainDecisions.push(action);this.session.decisionCount=this.session.brainDecisions.length;
    if(resuming){this.brainSignal('perception',{decision:sequence,phase:action.phase},false);if((observation.recentMarks?.length||0)||(observation.visitedAreas?.length||0)||action.motifReference)this.brainSignal('memory',{decision:sequence,phase:action.phase},false);if(action.evaluation)this.brainSignal('evaluation',{decision:sequence,summary:action.evaluation.summary},false);this.brainSignal('planning',{decision:sequence,movementStyle:action.movementStyle},false)}
    this.session.events.push({type:'brain_decision',timestamp:this.mechanics.clock,decision:sequence,intent:action.intent,phase:action.phase,movementStyle:action.movementStyle,brushTool:action.brushTool,technique:action.technique,brushDown:action.brushDown});
    if(action.evaluation){this.session.evaluationCheckpoints.push(clone(action.evaluation));this.session.events.push({type:'evaluate',timestamp:this.mechanics.clock,...clone(action.evaluation)})}
    if(action.intent==='FINISH_ARTWORK'){
      this.brainSignal('completion',{decision:sequence,phase:action.phase});
      this.mechanics.lift();this.session.status='EVALUATING';this.session.completionReason=action.reason;this.session.events.push({type:'state_change',timestamp:this.mechanics.clock,state:'EVALUATING'});this.session.events.push({type:'finish_artwork',timestamp:this.mechanics.clock,reason:action.reason});
      this.session.publicLogs.push({timestamp:formatClock(this.mechanics.clock),category:'STATE',message:'EVALUATING — the fly lifted her foreleg and ended drawing.'});return false;
    }
    this.brainSignal('action',{decision:sequence,movementStyle:action.movementStyle});const change=this.mechanics.execute(action,sequence);this.session.status='RUNNING';this.session.duration=this.mechanics.clock;this.session.physicalActionCount=this.mechanics.physicalActionCount;
    if(action.brushDown&&!this.session.markFamilies.includes(change.family))this.session.markFamilies.push(change.family);
    if(!resuming)this.session.publicLogs.push({timestamp:formatClock(this.mechanics.clock),category:'ACTION',message:`${action.phase}: ${action.movementStyle} · ${action.brushTool} · ${action.technique}. ${action.reason}`});return true;
  }
  async step(fetchImpl=fetch){
    if(this.finished||!['CREATED','RUNNING'].includes(this.session.status))return false;
    const sequence=this.session.brainDecisions.length;this.brainSignal('perception',{decision:sequence,phase:this.session.brainDecisions.at(-1)?.phase||'EXPLORATION'});
    const response=await fetchImpl(`/api/sessions/${this.session.sessionId}/decision`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sequence})});
    if(!response.ok)throw new Error(`brain decision failed (${response.status})`);
    const result=await response.json(),observation=result.observation||{};if((observation.recentMarks?.length||0)||(observation.visitedAreas?.length||0))this.brainSignal('memory',{decision:sequence,marks:observation.recentMarks?.length||0});if(result.action.evaluation)this.brainSignal('evaluation',{decision:sequence,summary:result.action.evaluation.summary});this.brainSignal('planning',{decision:sequence,movementStyle:result.action.movementStyle,phase:result.action.phase});return this.applyServerDecision(result);
  }
  async finalize(fetchImpl=fetch){
    if(!['EVALUATING','FINALIZING'].includes(this.session.status))throw new Error('The fly has not finished the artwork');
    this.session.status='FINALIZING';
    const response=await fetchImpl(`/api/sessions/${this.session.sessionId}/finalize`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({client_fingerprint:performanceFingerprint(this.session),artifact_reference:`server-authoritative:${this.session.sessionId}`})});
    if(!response.ok)throw new Error(`finalization failed (${response.status})`);
    const raw=await response.json();this.api=raw;const completed=apiToSession(raw);completed.brainDecisions=(raw.brain_decisions||[]).map(item=>clone(item.action));completed.observations=(raw.brain_decisions||[]).map(item=>clone(item.observation));completed.markFamilies=[...new Set(completed.events.filter(e=>e.type==='stroke').map(e=>e.family))];completed.publicLogs=[...this.session.publicLogs,{timestamp:formatClock(completed.duration),category:'STATE',message:'ARTWORK COMPLETE - the room has been archived.'}];this.session=completed;this.finished=true;return this.session;
  }
}

export async function createBackendPerformance(options={},fetchImpl=fetch){
  const response=await fetchImpl('/api/sessions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(options)});if(!response.ok)throw new Error('session start failed');return new BackendFlyPerformance(await response.json());
}
export async function resumeBackendPerformance(sessionId,fetchImpl=fetch){const response=await fetchImpl(`/api/sessions/${sessionId}`);if(!response.ok)throw new Error('session unavailable');return new BackendFlyPerformance(await response.json())}
export function executeRecordedPerformance(seed,actions,options={}){
  const raw={session_id:String(options.sessionId||seed),seed,status:'CREATED',brain_mode:options.brainMode||'RECORDED AUTHORITATIVE ACTIONS',parameters:options.parameters||{},limits:{},brain_decisions:[]};const runner=new BackendFlyPerformance(raw,{localMechanics:true});
  for(const action of actions){if(!runner.applyAction(action,null,true))break}return runner.session;
}
export function normalizePerformance(raw){if(!raw||!Array.isArray(raw.events))return{sessionId:'UNKNOWN',seed:0,status:'CREATED',brainMode:'UNAVAILABLE',duration:0,events:[],brainDecisions:[],observations:[],evaluationCheckpoints:[],markFamilies:[],description:'No session.'};return{...raw,sessionId:String(raw.sessionId||raw.session_id||raw.seed||'UNKNOWN').slice(0,64),duration:clamp(Number(raw.duration)||0,0,86400000),events:raw.events.filter(e=>e&&typeof e.type==='string')}}
export function performanceFingerprint(session){return hashSource({seed:session.seed,brainMode:session.brainMode,parameters:session.parameters,observations:session.observations,brainDecisions:session.brainDecisions,evaluationCheckpoints:session.evaluationCheckpoints,completionReason:session.completionReason,events:session.events})}

export function pointAlongPath(points,progress){if(!points.length)return[0,0];if(points.length===1||progress<=0)return[...points[0]];if(progress>=1)return[...points.at(-1)];const lengths=[];let total=0;for(let i=1;i<points.length;i++){const n=distance(points[i-1],points[i]);lengths.push(n);total+=n}let target=total*progress;for(let i=0;i<lengths.length;i++){if(target<=lengths[i]){const t=lengths[i]?target/lengths[i]:0;return[mix(points[i][0],points[i+1][0],t),mix(points[i][1],points[i+1][1],t)]}target-=lengths[i]}return[...points.at(-1)]}
export function frameAtTime(session,time){let handTip=[735,48],brushPoint=null,brushDown=false,activeEvent=null;for(const event of session.events){if(event.timestamp>time)break;const p=event.duration?clamp((time-event.timestamp)/event.duration,0,1):1;if(event.type==='move'){const t=ease(p);handTip=[mix(event.from[0],event.to[0],t),mix(event.from[1],event.to[1],t)];activeEvent=event}else if(event.type==='stroke'){handTip=pointAlongPath(event.points,ease(p));brushPoint=handTip;brushDown=p<1;activeEvent=event}else if(event.point){handTip=[...event.point];brushDown=event.type==='tip_down';activeEvent=event}}return{handTip,brushPoint,brushDown,activeEvent}}
export function solveForeleg(root,tip,upper=58,lower=68){const dx=tip[0]-root[0],dy=tip[1]-root[1],raw=Math.hypot(dx,dy)||.001,reach=clamp(raw,Math.abs(upper-lower)+.001,upper+lower-.001),direction=Math.atan2(dy,dx),shoulder=Math.acos(clamp((upper**2+reach**2-lower**2)/(2*upper*reach),-1,1)),angle=direction-shoulder;return{root:[...root],elbow:[root[0]+Math.cos(angle)*upper,root[1]+Math.sin(angle)*upper],tip:[...tip]}}
function visiblePath(points,progress){const target=pointAlongPath(points,progress),result=[points[0]],targetDistance=points.reduce((sum,p,i)=>i?sum+distance(points[i-1],p):sum,0)*progress;let walked=0;for(let i=1;i<points.length;i++){const segment=distance(points[i-1],points[i]);if(walked+segment>=targetDistance)break;result.push(points[i]);walked+=segment}result.push(target);return result}
function strokePath(ctx,points,dx=0,dy=0){ctx.beginPath();ctx.moveTo(points[0][0]+dx,points[0][1]+dy);for(const point of points.slice(1))ctx.lineTo(point[0]+dx,point[1]+dy);ctx.stroke()}
function techniqueMarks(ctx,event,points){
  const tool=event.brushTool||'ink_line',technique=event.technique||'continuous',seed=(event.decision||0)+1;
  if(tool==='stipple'||technique==='stippling'||tool==='splatter'){
    const count=tool==='splatter'?4:1;
    for(let i=0;i<points.length;i+=2)for(let dot=0;dot<count;dot++){const spread=tool==='splatter'?event.width*2.7:event.width*.45;const angle=Math.sin((seed*37+i*19+dot*53)*.91)*Math.PI*2;const radius=spread*(tool==='splatter'?(.25+((i+dot)%5)/5):.25);ctx.beginPath();ctx.arc(points[i][0]+Math.cos(angle)*radius,points[i][1]+Math.sin(angle)*radius,Math.max(.55,event.width*(tool==='splatter'?.11:.22)*(1+dot*.18)),0,Math.PI*2);ctx.fill()}
    return;
  }
  if(technique==='hatching'||technique==='cross_hatching'){
    ctx.lineWidth=Math.max(.55,event.width*.28);
    for(let i=1;i<points.length;i+=2){const a=points[i-1],p=points[i],angle=Math.atan2(p[1]-a[1],p[0]-a[0])+Math.PI/2,length=5+event.width*1.8;for(const flip of technique==='cross_hatching'?[1,-1]:[1]){ctx.beginPath();ctx.moveTo(p[0]-Math.cos(angle+.55*flip)*length,p[1]-Math.sin(angle+.55*flip)*length);ctx.lineTo(p[0]+Math.cos(angle+.55*flip)*length,p[1]+Math.sin(angle+.55*flip)*length);ctx.stroke()}}
    return;
  }
  if(tool==='wash'||tool==='soft_paint'||technique==='layered_glazing'){const base=ctx.globalAlpha;ctx.globalAlpha=Math.max(.58,base*.78);ctx.lineWidth=event.width*1.35;strokePath(ctx,points);ctx.globalAlpha=Math.max(.7,base*.94);ctx.lineWidth=event.width*.62;strokePath(ctx,points);return}
  if(tool==='dry_brush'||tool==='charcoal_grain'||technique==='smudged_dragging'){const base=ctx.globalAlpha;for(const offset of [-1,0,1]){ctx.globalAlpha=offset?Math.max(.56,base*.72):base;ctx.lineWidth=event.width*(offset? .24:.54);strokePath(ctx,points,offset*event.width*.34,offset*event.width*.22)}if(tool==='charcoal_grain'){ctx.fillStyle=ctx.strokeStyle;ctx.globalAlpha=Math.max(.55,base*.7);for(let i=1;i<points.length;i+=3)ctx.fillRect(points[i][0]+Math.sin(i*seed)*event.width,points[i][1]+Math.cos(i+seed)*event.width,.7,.7)}return}
  if(technique==='overpainting'){const base=ctx.globalAlpha;ctx.globalAlpha=Math.max(.58,base*.72);ctx.lineWidth=event.width*1.45;strokePath(ctx,points);ctx.globalAlpha=Math.max(.72,base*.94);ctx.lineWidth=event.width*.56;strokePath(ctx,points);return}
  strokePath(ctx,points);
}
function partialPath(ctx,event,progress){const target=pointAlongPath(event.points,progress),points=visiblePath(event.points,progress),correction=Boolean(event.erase)||event.brushTool==='subtractive';ctx.save();ctx.globalCompositeOperation='source-over';ctx.strokeStyle=correction?'#ffffff':event.color;ctx.fillStyle=correction?'#ffffff':event.color;ctx.globalAlpha=correction?1:event.opacity;ctx.lineWidth=event.width;ctx.lineCap='round';ctx.lineJoin='round';techniqueMarks(ctx,event,points);ctx.restore();return target}
function drawForeleg(ctx,tip,brushDown){const root=[clamp(tip[0]+82,95,770),clamp(tip[1]-86,28,450)],limb=solveForeleg(root,tip);ctx.save();ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#777';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(...limb.root);ctx.lineTo(...limb.elbow);ctx.lineTo(...limb.tip);ctx.stroke();const angle=Math.atan2(tip[1]-limb.elbow[1],tip[0]-limb.elbow[0]);ctx.strokeStyle=brushDown?'#fff':'#aaa';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(...tip);ctx.lineTo(tip[0]+Math.cos(angle+.8)*10,tip[1]+Math.sin(angle+.8)*10);ctx.moveTo(...tip);ctx.lineTo(tip[0]+Math.cos(angle-.8)*10,tip[1]+Math.sin(angle-.8)*10);ctx.stroke();ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(...tip,brushDown?3.2:2,0,Math.PI*2);ctx.fill();ctx.restore()}

function drawFullFly(ctx,tip,brushDown=false,time=0){
  const tx=clamp(Number(tip?.[0]??735),24,776);
  const ty=clamp(Number(tip?.[1]??48),24,476);

  // Compact, anatomical side-profile fly. The fly stays close to the active mark.
  const cx=clamp(tx-70,82,718);
  const cy=clamp(ty-27,58,442);
  const dx=tx-cx,dy=ty-cy;
  const reach=Math.max(48,Math.hypot(dx,dy));
  const angle=Math.atan2(dy,dx);
  const flap=brushDown?Math.sin(Number(time||0)/115)*.11:Math.sin(Number(time||0)/560)*.025;

  ctx.save();
  ctx.translate(cx,cy);
  ctx.rotate(angle);
  ctx.lineCap='round';
  ctx.lineJoin='round';

  // Wings sit high on the thorax and sweep backward like a real fruit fly.
  const wing=(yScale,alpha,rotation)=>{
    ctx.save();
    ctx.translate(-5,-8);
    ctx.scale(1,yScale);
    ctx.rotate(rotation+flap*yScale);
    ctx.globalAlpha=alpha;
    ctx.fillStyle='#b8b8b8';
    ctx.strokeStyle='#4c4c4c';
    ctx.lineWidth=1.25;
    ctx.beginPath();
    ctx.moveTo(1,0);
    ctx.bezierCurveTo(-10,-24,-37,-42,-64,-34);
    ctx.bezierCurveTo(-61,-17,-38,-4,-3,3);
    ctx.closePath();
    ctx.fill();ctx.stroke();

    ctx.strokeStyle='#666';
    ctx.lineWidth=.65;
    ctx.beginPath();
    ctx.moveTo(-2,0);ctx.lineTo(-48,-28);
    ctx.moveTo(-13,-8);ctx.lineTo(-45,-9);
    ctx.moveTo(-26,-17);ctx.lineTo(-31,-31);
    ctx.stroke();
    ctx.restore();
  };
  wing(-1,.09,-.06);
  wing(1,.24,.02);

  // Five support legs behind the body. Thin segmented geometry reads as insect anatomy.
  ctx.strokeStyle='#111';
  ctx.lineWidth=2.1;
  const supportLegs=[
    [[10,7],[22,18],[34,28],[44,29]],
    [[2,10],[-1,26],[-13,39],[-25,42]],
    [[-7,9],[-20,24],[-36,36],[-50,37]],
    [[0,7],[-10,23],[-25,30],[-38,28]],
    [[-14,7],[-30,18],[-45,23],[-58,20]],
  ];
  for(const pts of supportLegs){
    ctx.beginPath();
    ctx.moveTo(...pts[0]);
    for(const p of pts.slice(1))ctx.lineTo(...p);
    ctx.stroke();
  }

  // Natural tapered abdomen — no brush stuck to the rear anymore.
  ctx.fillStyle='#111';
  ctx.beginPath();
  ctx.moveTo(-9,-11);
  ctx.bezierCurveTo(-26,-16,-47,-13,-61,-5);
  ctx.bezierCurveTo(-68,-1,-68,3,-61,7);
  ctx.bezierCurveTo(-47,14,-25,15,-9,10);
  ctx.bezierCurveTo(-3,7,0,4,1,0);
  ctx.bezierCurveTo(0,-5,-3,-8,-9,-11);
  ctx.closePath();
  ctx.fill();

  // Subtle abdomen segmentation.
  ctx.strokeStyle='rgba(255,255,255,.15)';
  ctx.lineWidth=.75;
  for(const x of [-22,-34,-46,-56]){
    ctx.beginPath();
    ctx.moveTo(x,-9);
    ctx.quadraticCurveTo(x-2,0,x,9);
    ctx.stroke();
  }

  // Thorax has a slightly irregular insect shape instead of a perfect circle.
  ctx.fillStyle='#0b0b0b';
  ctx.beginPath();
  ctx.moveTo(-12,-16);
  ctx.bezierCurveTo(2,-22,16,-15,19,-3);
  ctx.bezierCurveTo(22,9,12,18,-2,19);
  ctx.bezierCurveTo(-16,18,-25,9,-24,-2);
  ctx.bezierCurveTo(-23,-10,-19,-14,-12,-16);
  ctx.closePath();
  ctx.fill();

  // Head + one bright eye preserve JPGFLY's graphic identity.
  ctx.fillStyle='#0a0a0a';
  ctx.beginPath();
  ctx.ellipse(24,-1,14,15,-.08,0,TAU);
  ctx.fill();

  ctx.fillStyle='#fff';
  ctx.beginPath();
  ctx.ellipse(29,-4,5.6,7.8,-.16,0,TAU);
  ctx.fill();
  ctx.strokeStyle='#222';
  ctx.lineWidth=1.2;
  ctx.stroke();

  // Antennae and small facial bristles.
  ctx.strokeStyle='#111';
  ctx.lineWidth=1.8;
  ctx.beginPath();
  ctx.moveTo(31,-12);ctx.quadraticCurveTo(39,-21,48,-24);
  ctx.moveTo(34,-9);ctx.quadraticCurveTo(45,-13,54,-11);
  ctx.stroke();
  ctx.lineWidth=1;
  ctx.beginPath();
  ctx.moveTo(35,3);ctx.lineTo(43,7);
  ctx.moveTo(34,6);ctx.lineTo(40,11);
  ctx.stroke();

  // Front leg grips an actual paintbrush instead of becoming a huge black limb.
  const gripX=Math.min(43,Math.max(31,reach*.53));
  const shoulder=[11,8],elbow=[23,22],grip=[gripX,12];

  ctx.strokeStyle='#111';
  ctx.lineWidth=2.4;
  ctx.beginPath();
  ctx.moveTo(...shoulder);
  ctx.lineTo(...elbow);
  ctx.lineTo(...grip);
  ctx.stroke();

  // Tiny tarsus curls around the handle.
  ctx.lineWidth=1.5;
  ctx.beginPath();
  ctx.moveTo(gripX-2,10);ctx.lineTo(gripX+3,14);
  ctx.moveTo(gripX,9);ctx.lineTo(gripX+5,12);
  ctx.stroke();

  // Paintbrush: dark handle, silver ferrule, tapered bristles ending exactly on the mark.
  const ferruleStart=Math.max(gripX+12,reach-15);
  const bristleStart=Math.max(ferruleStart+6,reach-7);

  ctx.strokeStyle='#171717';
  ctx.lineWidth=4.6;
  ctx.beginPath();
  ctx.moveTo(gripX,12);
  ctx.lineTo(ferruleStart,3);
  ctx.stroke();

  const grad=ctx.createLinearGradient(ferruleStart,-5,bristleStart,5);
  grad.addColorStop(0,'#efefef');
  grad.addColorStop(.32,'#777');
  grad.addColorStop(.66,'#d7d7d7');
  grad.addColorStop(1,'#555');
  ctx.fillStyle=grad;
  ctx.beginPath();
  ctx.moveTo(ferruleStart,-1);
  ctx.lineTo(bristleStart,-3.4);
  ctx.lineTo(bristleStart,4.6);
  ctx.lineTo(ferruleStart,7);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle='#333';
  ctx.lineWidth=.8;
  ctx.stroke();

  ctx.fillStyle=brushDown?'#111':'#2b2b2b';
  ctx.beginPath();
  ctx.moveTo(bristleStart,-3.2);
  ctx.bezierCurveTo(reach-3,-2.4,reach-1,-1.2,reach,0);
  ctx.bezierCurveTo(reach-1,1.4,reach-3,2.7,bristleStart,4.2);
  ctx.closePath();
  ctx.fill();

  // A few bristle strands keep the tip organic.
  ctx.strokeStyle=brushDown?'#111':'#3b3b3b';
  ctx.lineWidth=.7;
  ctx.beginPath();
  ctx.moveTo(bristleStart,-1.2);ctx.lineTo(reach,0);
  ctx.moveTo(bristleStart,1.2);ctx.lineTo(reach,0);
  ctx.stroke();

  ctx.restore();
}

export function renderForelegOverlay(ctx,tip,brushDown=false){ctx.save();ctx.setTransform(ctx.canvas.width/WIDTH,0,0,ctx.canvas.height/HEIGHT,0,0);drawForeleg(ctx,tip,brushDown);ctx.restore()}
export function renderFlyOverlay(ctx,tip,brushDown=false,time=0){ctx.save();ctx.setTransform(ctx.canvas.width/WIDTH,0,0,ctx.canvas.height/HEIGHT,0,0);drawFullFly(ctx,tip,brushDown,time);ctx.restore()}
export function renderPerformance(ctx,session,time,{showHand=true,clear=true}={}){if(clear){ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='#ffffff';ctx.fillRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.restore();}ctx.save();ctx.setTransform(ctx.canvas.width/WIDTH,0,0,ctx.canvas.height/HEIGHT,0,0);let handTip=[735,48],brushDown=false;for(const event of session.events){if(event.timestamp>time)break;const p=event.duration?clamp((time-event.timestamp)/event.duration,0,1):1;if(event.type==='clear'){ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='#ffffff';ctx.fillRect(0,0,ctx.canvas.width,ctx.canvas.height);ctx.restore()}else if(event.type==='move'){const t=ease(p);handTip=[mix(event.from[0],event.to[0],t),mix(event.from[1],event.to[1],t)];brushDown=false}else if(event.type==='stroke'){const paintProgress=ease(p);partialPath(ctx,event,paintProgress);handTip=pointAlongPath(event.points,clamp(paintProgress+.035,0,1));brushDown=p<1}else if(event.point){handTip=[...event.point];brushDown=event.type==='tip_down'}}if(showHand)drawForeleg(ctx,handTip,brushDown);ctx.restore();return{handTip:[...handTip],brushPoint:brushDown?[...handTip]:null,brushDown}}
