const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)||0));
const ease=(rate,dt)=>1-Math.exp(-rate*Math.max(0,dt));

const NEURAL_BG='#000000';
const FLYWIRE_COLORS=Object.freeze({
  optic:'#293857',central:'#73542a',sensory:'#245c57',visual_projection:'#1a7a9e',
  visual_centrifugal:'#61388c',descending:'#9e471a',ascending:'#33732e',motor:'#8c2424',endocrine:'#804066'
});
const CIRCUIT_COLORS=Object.freeze({
  visual:'#26d9ff',steering:'#ff8c1a',moonwalk:'#ff33cc',walk:'#40ff59',
  groom:'#bf8cff',escape:'#ff5940',giant_fiber:'#fff266',spike:'#bff2ff'
});
const NEURAL_PALETTE=[
  CIRCUIT_COLORS.visual,CIRCUIT_COLORS.steering,CIRCUIT_COLORS.moonwalk,CIRCUIT_COLORS.walk,
  CIRCUIT_COLORS.groom,CIRCUIT_COLORS.escape,CIRCUIT_COLORS.giant_fiber,
  FLYWIRE_COLORS.sensory,FLYWIRE_COLORS.visual_centrifugal,FLYWIRE_COLORS.ascending
];
function hexRgba(hex,alpha=1){
  const raw=String(hex||'#1a7a9e').replace('#','');
  const n=parseInt(raw.length===3?raw.split('').map(ch=>ch+ch).join(''):raw,16);
  const r=(n>>16)&255,g=(n>>8)&255,b=n&255;
  return `rgba(${r},${g},${b},${Math.max(0,Math.min(1,alpha))})`;
}

function hash01(value){
  let h=2166136261>>>0;
  const s=String(value??'');
  for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}
  return h/4294967295;
}
function zebraColor(id){return NEURAL_PALETTE[Math.floor(hash01(id)*NEURAL_PALETTE.length)%NEURAL_PALETTE.length];}

export class ZebraNeuralActivityView{
  constructor(canvas,statusNode){
    this.canvas=canvas;
    this.statusNode=statusNode;
    this.ctx=canvas.getContext('2d',{alpha:false});
    this.state={
      ok:true,enabled:false,connected:false,status:'BACKBONE_ONLY',
      activity_loaded:false,biological_data_loaded:false,connectome_loaded:false,
      dataset:'',sampled_neurons:0,total_neurons:0,nodes:[],signals:{}
    };
    this.nodes=new Map();
    this.functionalEdges=[];
    this.pathPulses=[];
    this.displaySignals={};
    this.running=false;
    this.lastFrame=performance.now();
    this.lastDrawAt=0;
    this.resize();
  }

  pushState(state={}){
    if(!(state&&typeof state==='object'))return;
    this.state={...this.state,...state};

    const incoming=Array.isArray(state.nodes)?state.nodes:[];
    const seen=new Set();
    for(const raw of incoming){
      const id=String(raw.id??raw.neuron_id??`${raw.x}:${raw.y}`);
      seen.add(id);
      const existing=this.nodes.get(id)||{
        id,color:zebraColor(id),x:clamp(raw.x),y:clamp(raw.y),activity:0,
        tx:clamp(raw.x),ty:clamp(raw.y),ta:0
      };
      existing.tx=clamp(raw.x);
      existing.ty=clamp(raw.y);
      existing.ta=clamp(raw.activity);
      this.nodes.set(id,existing);
    }
    for(const [id,node] of this.nodes){
      if(!seen.has(id))node.ta=0;
    }
    this.buildFunctionalPaths(incoming);

    const signals=state.signals||{};
    for(const [key,value] of Object.entries(signals)){
      if(!Number.isFinite(this.displaySignals[key]))this.displaySignals[key]=clamp(value);
    }

    this.syncStatus();
    this.schedule();
  }

  buildFunctionalPaths(incoming=[]){
    // ZAPBench supplies real calcium traces but this JPGFLY service does not
    // load an anatomical connectome. These are therefore functional display
    // paths between simultaneously active sampled neurons, never claimed as synapses.
    const hot=incoming
      .filter(node=>Number(node.activity||0)>.16)
      .sort((a,b)=>Number(b.activity||0)-Number(a.activity||0))
      .slice(0,42);
    const edges=[];const used=new Set();
    for(let i=0;i<hot.length;i++){
      const a=hot[i];let best=null,bestScore=Infinity;
      for(let j=0;j<hot.length;j++){
        if(i===j)continue;
        const b=hot[j];
        const dx=Number(a.x)-Number(b.x),dy=Number(a.y)-Number(b.y);
        const activityGap=Math.abs(Number(a.activity||0)-Number(b.activity||0));
        const score=Math.hypot(dx,dy)+activityGap*.34;
        if(score<bestScore){bestScore=score;best=b;}
      }
      if(!best)continue;
      const sa=String(a.id??a.neuron_id),sb=String(best.id??best.neuron_id);
      const key=sa<sb?sa+'>'+sb:sb+'>'+sa;
      if(used.has(key))continue;
      used.add(key);edges.push({source:sa,target:sb,strength:clamp((Number(a.activity||0)+Number(best.activity||0))*.5)});
    }
    this.functionalEdges=edges.slice(0,58);
    const now=performance.now();
    this.pathPulses=this.functionalEdges.slice(0,28).map((edge,index)=>({
      ...edge,start:now+index*18,life:420+edge.strength*260,color:zebraColor(edge.source)
    }));
  }

  syncStatus(){
    if(!this.statusNode)return;
    const s=this.state||{};
    const loaded=!!(s.connected&&(s.biological_data_loaded||s.activity_loaded||s.connectome_loaded));
    if(loaded){
      const sampled=Number(s.sampled_neurons||0)||this.nodes.size;
      const total=Number(s.total_neurons||0);
      this.statusNode.textContent=`LIVE · ${s.dataset||'ZAPBENCH'} · ${sampled}${total?` / ${total}`:''} sampled neurons`;
    }else if(s.enabled&&s.status==='LOCAL_ENGINE_OFFLINE'){
      this.statusNode.textContent='ZEBRACNS LOCAL ENGINE OFFLINE';
    }else if(s.enabled&&s.connected){
      this.statusNode.textContent='ZEBRACNS ONLINE · REAL ACTIVITY DATA NOT LOADED';
    }else{
      this.statusNode.textContent='WAITING FOR REAL ZAPBENCH ACTIVITY';
    }
  }

  resize(){
    const box=this.canvas.getBoundingClientRect();
    this.dpr=Math.min(1.25,window.devicePixelRatio||1);
    this.canvas.width=Math.max(1,Math.round(box.width*this.dpr));
    this.canvas.height=Math.max(1,Math.round(Math.max(240,box.height)*this.dpr));
    this.ctx.setTransform(this.dpr,0,0,this.dpr,0,0);
    this.draw();
  }

  schedule(){
    if(this.running)return;
    this.running=true;
    this.lastFrame=performance.now();
    requestAnimationFrame(this.tick);
  }

  tick=(now)=>{
    const dt=Math.min(.05,Math.max(.001,(now-this.lastFrame)/1000));
    this.lastFrame=now;
    const fast=ease(9,dt);
    const slow=ease(5,dt);
    let active=false;

    for(const node of this.nodes.values()){
      const nx=node.x+(node.tx-node.x)*slow;
      const ny=node.y+(node.ty-node.y)*slow;
      const na=node.activity+(node.ta-node.activity)*fast;
      if(Math.abs(nx-node.tx)>.0007||Math.abs(ny-node.ty)>.0007||Math.abs(na-node.ta)>.002)active=true;
      node.x=nx;node.y=ny;node.activity=na;
    }

    const signals=this.state?.signals||{};
    for(const key of new Set([...Object.keys(this.displaySignals),...Object.keys(signals)])){
      const target=clamp(signals[key]);
      const current=Number.isFinite(this.displaySignals[key])?this.displaySignals[key]:target;
      const next=current+(target-current)*slow;
      if(Math.abs(next-target)>.002)active=true;
      this.displaySignals[key]=next;
    }

    this.pathPulses=this.pathPulses.filter(pulse=>now<pulse.start+pulse.life);
    if(this.pathPulses.length)active=true;
    const loaded=!!(this.state?.connected&&(this.state?.biological_data_loaded||this.state?.activity_loaded||this.state?.connectome_loaded));
    const hasLiveActivity=loaded&&[...this.nodes.values()].some(node=>node.activity>.015||node.ta>.015);

    if(now-this.lastDrawAt>=48){
      this.lastDrawAt=now;
      this.draw(now);
    }

    if(document.hidden){
      this.running=false;
    }else if(active||hasLiveActivity){
      setTimeout(()=>requestAnimationFrame(this.tick),48);
    }else{
      this.running=false;
      this.draw(now);
    }
  };

  label(text,x,y,alpha=.65,size=8){
    const c=this.ctx;
    c.fillStyle=hexRgba(CIRCUIT_COLORS.spike,alpha);
    c.font=`${size}px ui-monospace,SFMono-Regular,Consolas,monospace`;
    c.fillText(String(text),x,y);
  }

  draw(now=performance.now()){
    const c=this.ctx;
    const dpr=this.dpr||1;
    const w=this.canvas.width/dpr,h=this.canvas.height/dpr;
    c.setTransform(dpr,0,0,dpr,0,0);
    c.fillStyle=NEURAL_BG;
    c.fillRect(0,0,w,h);

    const s=this.state||{};
    const loaded=!!(s.connected&&(s.biological_data_loaded||s.activity_loaded||s.connectome_loaded));

    const firing=loaded&&[...this.nodes.values()].some(node=>node.activity>.015||node.ta>.015);
    this.label('ZEBRACNS · REAL ZAPBENCH CALCIUM ACTIVITY',12,18,loaded?.95:.50,9);
    this.label(
      firing?`LIVE FIRING · FRAME ${Number(s.frame||0)}`:(loaded?`CONNECTED / QUIET · FRAME ${Number(s.frame||0)}`:'NO BIOLOGICAL ACTIVITY SHOWN'),
      12,31,
      firing?.82:(loaded?.55:.34),
      7
    );

    const top=46,bottom=h-42,left=14,right=w-14;
    c.strokeStyle='rgba(255,255,255,.14)';
    c.lineWidth=1;
    c.strokeRect(left,top,right-left,bottom-top);

    if(loaded&&this.nodes.size){
      for(const edge of this.functionalEdges){
        const a=this.nodes.get(edge.source),b=this.nodes.get(edge.target);
        if(!a||!b)continue;
        const color=zebraColor(edge.source);
        c.strokeStyle=hexRgba(color,.09+.22*edge.strength);
        c.lineWidth=.45+edge.strength*.65;
        c.beginPath();
        c.moveTo(left+a.x*(right-left),top+a.y*(bottom-top));
        c.lineTo(left+b.x*(right-left),top+b.y*(bottom-top));
        c.stroke();
      }
      for(const pulse of this.pathPulses){
        if(now<pulse.start)continue;
        const a=this.nodes.get(pulse.source),b=this.nodes.get(pulse.target);
        if(!a||!b)continue;
        const t=clamp((now-pulse.start)/pulse.life);
        const x=left+(a.x+(b.x-a.x)*t)*(right-left);
        const y=top+(a.y+(b.y-a.y)*t)*(bottom-top);
        const glow=5+pulse.strength*7;
        const g=c.createRadialGradient(x,y,0,x,y,glow);
        g.addColorStop(0,hexRgba(pulse.color,.92));
        g.addColorStop(1,hexRgba(pulse.color,0));
        c.fillStyle=g;c.beginPath();c.arc(x,y,glow,0,Math.PI*2);c.fill();
        c.fillStyle=pulse.color;c.beginPath();c.arc(x,y,1.3+pulse.strength*1.8,0,Math.PI*2);c.fill();
      }
      for(const node of this.nodes.values()){
        const x=left+node.x*(right-left);
        const y=top+node.y*(bottom-top);
        const a=clamp(node.activity);
        const pulse=.88+.12*Math.sin(now/180+(node.x*13+node.y*17));
        const radius=.8+a*2.6;

        const color=node.color||zebraColor(node.id);
        if(a>.42){
          c.beginPath();
          c.fillStyle=hexRgba(color,.08+a*.20);
          c.arc(x,y,radius*3.4*pulse,0,Math.PI*2);
          c.fill();
        }

        c.beginPath();
        c.fillStyle=hexRgba(color,.30+a*.70);
        c.arc(x,y,radius*pulse,0,Math.PI*2);
        c.fill();
      }
    }else{
      this.label('REAL ACTIVITY DATA REQUIRED',left+14,top+28,.34,9);
      this.label('This panel stays dormant instead of inventing neural activity.',left+14,top+46,.27,7);
    }

    const keys=['visual_salience','arousal','persistence','novelty_seek','attention_lock','state_instability','completion_pressure'];
    const usable=keys.filter(key=>Number.isFinite(Number(this.displaySignals[key])));
    if(usable.length){
      const gap=6;
      const gaugeW=Math.max(22,((right-left)-gap*(usable.length-1))/usable.length);
      const gy=h-25;
      usable.forEach((key,i)=>{
        const value=clamp(this.displaySignals[key]);
        const x=left+i*(gaugeW+gap);
        const color=NEURAL_PALETTE[i%NEURAL_PALETTE.length];
        c.fillStyle=hexRgba(color,.12);
        c.fillRect(x,gy,gaugeW,4);
        c.fillStyle=hexRgba(color,.42+value*.58);
        c.fillRect(x,gy,gaugeW*value,4);
        this.label(key.replaceAll('_',' ').slice(0,11).toUpperCase(),x,gy-5,.32,6);
      });
    }
  }
}
