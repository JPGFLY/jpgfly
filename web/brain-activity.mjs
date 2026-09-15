const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const lerp=(a,b,t)=>a+(b-a)*t;
const TAU=Math.PI*2;

const STAGES=[
  {key:'sense',label:'SENSE',sub:'CANVAS + MEMORY',x:.14},
  {key:'plan',label:'PLAN',sub:'PHASE + REGION + MOTIF',x:.39},
  {key:'paint',label:'PAINT',sub:'BRUSH + MOTION',x:.65},
  {key:'speak',label:'SPEAK',sub:'PUBLIC VOICE',x:.87},
];

const KEY_STAGE={
  perception:'sense',memory:'sense',
  phase:'plan',region:'plan',macro:'plan',strategy:'plan',motif:'plan',finish:'plan',
  brush:'paint',technique:'paint',pressure:'paint',motion:'paint',action:'paint',
  provider:'speak',noteQueue:'speak',recentNote:'speak'
};

const ROUTE=['perception','memory','phase','region','macro','strategy','motif','brush','technique','pressure','motion','action'];

export function signalsForDecision(observation={},action={}){
  const signals=['perception'];
  if(observation?.recentMarks?.length||observation?.visitedAreas?.length||action?.motifReference)signals.push('memory');
  if(action?.evaluation)signals.push('evaluation');
  signals.push('planning');
  signals.push(action?.intent==='FINISH_ARTWORK'?'completion':'action');
  return signals;
}

function seeded(seed){
  let s=seed>>>0;
  return()=>((s=(Math.imul(s,1664525)+1013904223)>>>0)/4294967296);
}

function makeNeuron(rand,cx,cy,scale,index){
  const z=.20+rand()*.80;
  const segments=[];

  function branch(x,y,theta,length,depth){
    let px=x,py=y;
    const steps=2+Math.floor(rand()*2);
    for(let i=0;i<steps;i++){
      const a=theta+(rand()-.5)*.34;
      const nx=px+Math.cos(a)*length*(.78+rand()*.20);
      const ny=py+Math.sin(a)*length*(.78+rand()*.20);
      segments.push({a:[px,py],b:[nx,ny],depth});
      px=nx;py=ny;
      if(depth<2&&rand()>(depth===0?.30:.58)){
        const spread=(rand()>.5?1:-1)*(.40+rand()*.42);
        branch(px,py,a+spread,length*(.52+rand()*.12),depth+1);
      }
    }
  }

  const roots=4+Math.floor(rand()*2);
  for(let r=0;r<roots;r++){
    const theta=r/roots*TAU+(rand()-.5)*.42;
    branch(cx,cy,theta,scale*(.16+rand()*.05),0);
  }

  // One long axon-like process gives the tree a readable direction.
  const direction=index%2?1:-1;
  let ax=cx,ay=cy;
  const theta=(direction>0?0:Math.PI)+(rand()-.5)*.35;
  for(let i=0;i<4;i++){
    const nx=ax+Math.cos(theta+(rand()-.5)*.16)*scale*(.19+rand()*.05);
    const ny=ay+Math.sin(theta+(rand()-.5)*.16)*scale*(.12+rand()*.04);
    segments.push({a:[ax,ay],b:[nx,ny],depth:0,axon:true});
    ax=nx;ay=ny;
  }

  return{cx,cy,z,segments,energy:0,stage:null};
}

export class BrainActivityView{
  constructor(canvas,status){
    this.canvas=canvas;
    this.ctx=canvas.getContext('2d',{alpha:false});
    this.status=status;
    this.history=[];
    this.language={provider:'PROCEDURAL',pending:false,note_count:0,last_note:''};
    this.neurons=[];
    this.stageIndices={sense:[],plan:[],paint:[],speak:[]};
    this.stageEnergy={sense:0,plan:0,paint:0,speak:0};
    this.semanticMap={};
    this.branchPulses=[];
    this.flowPulses=[];
    this.running=false;
    this.lastNow=0;
    this.staticLayer=document.createElement('canvas');
    this.buildNetwork();
    this.resize();
  }

  buildNetwork(){
    const rand=seeded(0x4a504746);
    const rows=3,cols=4;
    STAGES.forEach((stage,stageIndex)=>{
      for(let i=0;i<12;i++){
        const col=i%cols,row=Math.floor(i/cols);
        const jitterX=(rand()-.5)*.018,jitterY=(rand()-.5)*.028;
        const cx=stage.x+(col-1.5)*.035+jitterX;
        const cy=.42+(row-1)*.17+jitterY;
        const neuron=makeNeuron(rand,cx,cy,.22+rand()*.035,stageIndex*12+i);
        neuron.stage=stage.key;
        const index=this.neurons.push(neuron)-1;
        this.stageIndices[stage.key].push(index);
      }
    });

    const keys=Object.keys(KEY_STAGE);
    keys.forEach((key,keyIndex)=>{
      const stage=KEY_STAGE[key];
      const pool=this.stageIndices[stage];
      const local=keys.filter(k=>KEY_STAGE[k]===stage).indexOf(key);
      const start=(local*3+keyIndex)%pool.length;
      this.semanticMap[key]=[
        pool[start%pool.length],
        pool[(start+4)%pool.length],
        pool[(start+8)%pool.length]
      ];
    });
  }

  resize(){
    const box=this.canvas.getBoundingClientRect();
    const w=Math.max(1,Math.round(box.width));
    const h=Math.max(1,Math.round(box.height));
    this.canvas.width=w;this.canvas.height=h;
    this.staticLayer.width=w;this.staticLayer.height=h;
    this.renderStatic();
    this.draw(performance.now());
  }

  renderStatic(){
    const ctx=this.staticLayer.getContext('2d',{alpha:false});
    const w=this.staticLayer.width,h=this.staticLayer.height;
    ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);

    // Clear causal spine: SENSE -> PLAN -> PAINT, with PLAN -> SPEAK.
    ctx.strokeStyle='rgba(255,255,255,.12)';
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(STAGES[0].x*w,.16*h);
    ctx.lineTo(STAGES[1].x*w,.16*h);
    ctx.lineTo(STAGES[2].x*w,.16*h);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(STAGES[1].x*w,.16*h);
    ctx.lineTo(STAGES[3].x*w,.16*h);
    ctx.stroke();

    for(let i=0;i<STAGES.length;i++){
      const stage=STAGES[i],x=stage.x*w;
      ctx.textAlign='center';
      ctx.font='700 10px Consolas,monospace';
      ctx.fillStyle='rgba(255,255,255,.70)';
      ctx.fillText(stage.label,x,18);
      ctx.font='7px Consolas,monospace';
      ctx.fillStyle='rgba(255,255,255,.30)';
      ctx.fillText(stage.sub,x,30);

      if(i<2){
        const nx=STAGES[i+1].x*w;
        ctx.fillStyle='rgba(255,255,255,.22)';
        ctx.beginPath();
        ctx.moveTo(nx-7,.16*h-3);
        ctx.lineTo(nx-1,.16*h);
        ctx.lineTo(nx-7,.16*h+3);
        ctx.closePath();ctx.fill();
      }
    }

    // Faint separators make the functional groups readable without boxes.
    ctx.strokeStyle='rgba(255,255,255,.045)';
    ctx.setLineDash([3,5]);
    for(const x of [.265,.52,.76]){
      ctx.beginPath();ctx.moveTo(x*w,.22*h);ctx.lineTo(x*w,.83*h);ctx.stroke();
    }
    ctx.setLineDash([]);

    // Dormant morphology trees are static and cheap.
    for(const neuron of this.neurons){
      const alpha=.020+neuron.z*.032;
      ctx.strokeStyle='rgba(255,255,255,'+alpha+')';
      ctx.lineWidth=.34+neuron.z*.30;
      for(const seg of neuron.segments){
        ctx.beginPath();
        ctx.moveTo(seg.a[0]*w,seg.a[1]*h);
        ctx.lineTo(seg.b[0]*w,seg.b[1]*h);
        ctx.stroke();
      }
      ctx.fillStyle='rgba(255,255,255,'+(.045+neuron.z*.04)+')';
      ctx.beginPath();ctx.arc(neuron.cx*w,neuron.cy*h,.7+neuron.z*.45,0,TAU);ctx.fill();
    }

    ctx.textAlign='left';
    ctx.font='8px Consolas,monospace';
    ctx.fillStyle='rgba(255,255,255,.30)';
    ctx.fillText('MORPHOLOGY-INSPIRED VISUAL PROXY',12,h-11);
    ctx.textAlign='right';
    ctx.fillText('FULL FLM GRAPH: 166,700 NODES / 25,582,938 CONNECTIONS',w-12,h-11);
  }

  activateStage(stage,intensity=.8){
    this.stageEnergy[stage]=Math.max(this.stageEnergy[stage]||0,intensity);
  }

  fireNeuron(index,intensity=.8,delay=0){
    const neuron=this.neurons[index];
    if(!neuron)return;
    neuron.energy=Math.max(neuron.energy,intensity);

    const candidates=neuron.segments.filter(s=>s.axon||s.depth<=1);
    if(candidates.length){
      const seg=candidates[(index+this.history.length)%candidates.length];
      this.branchPulses.push({neuron:index,segment:seg,start:performance.now()+delay,life:270,strength:intensity});
    }
    this.branchPulses=this.branchPulses.slice(-42);
    this.schedule();
  }

  burst(key,intensity=.8,delay=0){
    const stage=KEY_STAGE[key];
    if(stage)this.activateStage(stage,intensity);
    const set=this.semanticMap[key]||[];
    set.forEach((index,i)=>this.fireNeuron(index,intensity,delay+i*28));
  }

  flow(from,to,delay=0,intensity=.8){
    const a=STAGES.find(s=>s.key===from),b=STAGES.find(s=>s.key===to);
    if(!a||!b)return;
    this.flowPulses.push({from:a.x,to:b.x,start:performance.now()+delay,life:360,strength:intensity});
    this.flowPulses=this.flowPulses.slice(-18);
    this.schedule();
  }

  signal(cluster,payload={}){
    const map={perception:'perception',memory:'memory',evaluation:'phase',planning:'macro',action:'action',completion:'finish'};
    const key=map[cluster]||cluster;
    this.burst(key,.84);
    if(this.status)this.status.textContent='RECORDED / '+String(key).toUpperCase()+' / '+(payload.phase||payload.movementStyle||payload.brushTool||'ACTIVE');
  }

  pushDecision(record){
    const action=record?.action||record||{};
    this.history.push({action,at:performance.now()});
    this.history=this.history.slice(-24);

    const pressure=clamp(Number(action.pressure||0));
    const weight=.58+pressure*.22;
    const moving=action.brushDown!==false;

    // Always show the causal story first.
    this.flow('sense','plan',70,weight);
    if(moving)this.flow('plan','paint',360,weight);

    const route=moving
      ?['perception','memory','phase','region','macro','motif','brush','technique','pressure','motion','action']
      :['perception','memory','phase','region','macro','motion'];

    route.forEach((key,index)=>this.burst(key,weight,index*64));
    if(action.intent==='FINISH_ARTWORK')this.burst('finish',1,300);

    if(this.status){
      this.status.textContent='SENSE -> PLAN -> '+(moving?'PAINT':'MOVE')+' / '+(action.brushTool||'TOOL');
    }
  }

  setLanguageState(state={}){
    const wasPending=Boolean(this.language.pending);
    this.language={...this.language,...state};
    if(this.language.pending&&!wasPending){
      this.flow('plan','speak',60,.95);
      this.burst('provider',.95,120);
      this.burst('noteQueue',.90,210);
    }
  }

  pushComment(comment={}){
    const provider=String(comment.provider||this.language.provider||'VOICE').toUpperCase();
    this.flow('plan','speak',40,.95);
    this.burst('provider',.92,100);
    this.burst('recentNote',1,190);
    this.burst('memory',.70,330);
    if(this.status)this.status.textContent='PLAN -> SPEAK / '+provider+' NOTE PUBLISHED';
  }

  schedule(){
    if(this.running)return;
    this.running=true;
    const tick=now=>{
      const dt=Math.min(50,Math.max(8,now-(this.lastNow||now)));
      this.lastNow=now;
      let active=false;

      for(const neuron of this.neurons){
        neuron.energy*=Math.pow(.87,dt/16.67);
        if(neuron.energy>.025)active=true;else neuron.energy=0;
      }
      for(const key of Object.keys(this.stageEnergy)){
        this.stageEnergy[key]*=Math.pow(.89,dt/16.67);
        if(this.stageEnergy[key]>.025)active=true;else this.stageEnergy[key]=0;
      }

      this.branchPulses=this.branchPulses.filter(p=>now<p.start+p.life);
      this.flowPulses=this.flowPulses.filter(p=>now<p.start+p.life);
      if(this.branchPulses.length||this.flowPulses.length)active=true;

      this.draw(now);
      if(active)requestAnimationFrame(tick);
      else{this.running=false;this.lastNow=0;}
    };
    requestAnimationFrame(tick);
  }

  draw(now){
    const ctx=this.ctx,w=this.canvas.width,h=this.canvas.height;
    ctx.drawImage(this.staticLayer,0,0);

    // Stage labels light up, so viewers can tell what the firing means.
    for(const stage of STAGES){
      const e=this.stageEnergy[stage.key]||0;
      if(e<.04)continue;
      const x=stage.x*w;
      ctx.textAlign='center';
      ctx.font='700 10px Consolas,monospace';
      ctx.fillStyle='rgba(255,255,255,'+clamp(.45+e*.50,.45,1)+')';
      ctx.fillText(stage.label,x,18);
      ctx.strokeStyle='rgba(255,255,255,'+clamp(.18+e*.45,.18,.78)+')';
      ctx.lineWidth=1.2;
      ctx.beginPath();ctx.moveTo(x-28,35);ctx.lineTo(x+28,35);ctx.stroke();
    }

    // Light the morphology trees assigned to the active functional group.
    for(const neuron of this.neurons){
      const e=neuron.energy;
      if(e<.07)continue;
      ctx.strokeStyle='rgba(255,255,255,'+clamp(.18+e*.67,.18,.92)+')';
      ctx.lineWidth=.48+neuron.z*.45+e*.30;
      for(const seg of neuron.segments){
        ctx.beginPath();
        ctx.moveTo(seg.a[0]*w,seg.a[1]*h);
        ctx.lineTo(seg.b[0]*w,seg.b[1]*h);
        ctx.stroke();
      }
      ctx.fillStyle='rgba(255,255,255,'+clamp(.38+e*.50,.38,.96)+')';
      ctx.beginPath();ctx.arc(neuron.cx*w,neuron.cy*h,1+neuron.z*.6+e*.5,0,TAU);ctx.fill();
    }

    // Signals traveling inside individual neuron morphologies.
    for(const p of this.branchPulses){
      if(now<p.start)continue;
      const t=clamp((now-p.start)/p.life),seg=p.segment;
      const x=lerp(seg.a[0],seg.b[0],t)*w,y=lerp(seg.a[1],seg.b[1],t)*h;
      const z=this.neurons[p.neuron].z;
      ctx.fillStyle='rgba(255,255,255,'+clamp(.35+p.strength*.55,.35,.96)+')';
      ctx.beginPath();ctx.arc(x,y,1.15+z*.55,0,TAU);ctx.fill();
    }

    // Big causal pulses make the relationship to JPGFLY's actions unmistakable.
    for(const p of this.flowPulses){
      if(now<p.start)continue;
      const t=clamp((now-p.start)/p.life);
      const x=lerp(p.from,p.to,t)*w,y=.16*h;
      ctx.fillStyle='rgba(255,255,255,'+clamp(.40+p.strength*.50,.40,.98)+')';
      ctx.beginPath();ctx.arc(x,y,2.3,0,TAU);ctx.fill();
    }

    ctx.textAlign='right';
    ctx.font='8px Consolas,monospace';
    ctx.fillStyle='rgba(255,255,255,.28)';
    ctx.fillText('48 MORPHOLOGY TREES / '+this.history.length+' RECENT DECISIONS',w-12,h-25);
  }
}
