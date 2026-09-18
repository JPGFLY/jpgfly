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
  for(let i=0;i<s.length;i++){
    h^=s.charCodeAt(i);
    h=Math.imul(h,16777619)>>>0;
  }
  return h/4294967295;
}

function nodeColor(node={}){
  const role=String(node.role||node.cell_type||node.superclass||node.class||'').toLowerCase();
  if(role.includes('giant')||role==='gf')return CIRCUIT_COLORS.giant_fiber;
  if(role.includes('visual')||role.includes('lc4')||role.includes('lplc2'))return CIRCUIT_COLORS.visual;
  if(role.includes('descending')||role.includes('dna'))return CIRCUIT_COLORS.steering;
  if(role.includes('motor'))return FLYWIRE_COLORS.motor;
  if(role.includes('ascending'))return FLYWIRE_COLORS.ascending;
  if(role.includes('sensory'))return FLYWIRE_COLORS.sensory;
  for(const [key,color] of Object.entries(FLYWIRE_COLORS))if(role.includes(key))return color;
  const id=node.body_id??node.id??node.neuron_id??'node';
  return NEURAL_PALETTE[Math.floor(hash01(id)*NEURAL_PALETTE.length)%NEURAL_PALETTE.length];
}

function activeId(item){
  if(item&&typeof item==='object'){
    return item.body_id??item.id??item.neuron_id??item.neuron??item.node_id??null;
  }
  if(Array.isArray(item))return item[0];
  return item;
}

function activeStrength(item){
  if(item&&typeof item==='object'){
    return clamp(item.activity??item.strength??item.spikes??item.value??1);
  }
  if(Array.isArray(item))return clamp(item[1]??1);
  return 1;
}

export class MaleCNSOverlay{
  constructor(canvas){
    this.canvas=canvas;
    this.ctx=canvas.getContext('2d',{alpha:false});
    this.state={ok:false,top_active:[],bias:{}};
    this.targetState=this.state;
    this.displayBias={};
    this.network={ok:false,nodes:[],edges:[]};
    this.positions=new Map();
    this.activeVisual=new Map();
    this.nodeById=new Map();
    this.pathPulses=[];
    this.staticLayer=document.createElement('canvas');
    this.running=false;
    this.lastFrame=performance.now();
    this.lastDrawAt=0;
    this.resize();
  }

  resize(){
    const box=this.canvas.getBoundingClientRect();
    this.dpr=Math.min(1.25,window.devicePixelRatio||1);
    this.canvas.width=Math.max(1,Math.round(box.width*this.dpr));
    this.canvas.height=Math.max(1,Math.round(box.height*this.dpr));
    this.ctx.setTransform(this.dpr,0,0,this.dpr,0,0);
    this.buildStaticLayer();
    this.draw();
  }

  setNetwork(data={}){
    const nodes=Array.isArray(data?.nodes)?data.nodes:[];
    const edges=Array.isArray(data?.edges)?data.edges:[];
    const signature=`${nodes.length}:${edges.length}:${data?.telemetry_schema||''}`;
    if(this.network.signature===signature&&nodes.length===this.network.nodes.length)return;
    this.network={
      ok:!!data?.ok,
      nodes,
      edges,
      telemetry_schema:data?.telemetry_schema||'',
      signature,
    };
    this.nodeById=new Map(nodes.map((node,i)=>[String(node.body_id??node.id??i),node]));
    this.layoutNetwork();
    this.buildStaticLayer();
    this.schedule();
  }

  pushState(state={}){
    this.targetState=state&&typeof state==='object'?state:{ok:false,top_active:[],bias:{}};
    this.state={...this.state,...this.targetState};
    const nextIds=new Set();
    for(const item of (Array.isArray(this.targetState.top_active)?this.targetState.top_active:[])){
      const id=activeId(item);
      if(id===null||id===undefined)continue;
      const key=String(id);
      nextIds.add(key);
      const existing=this.activeVisual.get(key)||{value:0,target:0};
      existing.target=Math.max(.12,activeStrength(item));
      this.activeVisual.set(key,existing);
    }
    for(const [key,value] of this.activeVisual){
      if(!nextIds.has(key))value.target=0;
    }
    this.seedPathPulses(nextIds);
    this.schedule();
  }

  seedPathPulses(activeIds){
    const edges=this.network.edges||[];
    if(!edges.length||!activeIds?.size)return;
    const now=performance.now();
    const start=Math.floor(now/97)%Math.max(1,edges.length);
    let added=0;
    for(let offset=0;offset<edges.length&&added<30;offset++){
      const edge=edges[(start+offset)%edges.length];
      const source=String(edge.source),target=String(edge.target);
      if(!activeIds.has(source)&&!activeIds.has(target))continue;
      if(!this.positions.has(source)||!this.positions.has(target))continue;
      const strength=clamp(Math.abs(Number(edge.weight)||1)/12,.22,1);
      const sourceNode=this.nodeById.get(source)||this.nodeById.get(target)||{};
      this.pathPulses.push({
        source,target,start:now+added*16,life:360+strength*280,
        strength,color:nodeColor(sourceNode)
      });
      added+=1;
    }
    this.pathPulses=this.pathPulses.slice(-84);
  }

  pushActivity(activity={}){
    this.targetState={
      ...this.targetState,
      ok:true,
      bias:{...(this.targetState.bias||{}),...(activity||{})},
    };
    this.state={...this.state,ok:true};
    this.schedule();
  }

  layoutNetwork(){
    const nodes=this.network.nodes||[];
    const edges=this.network.edges||[];
    if(!nodes.length){this.positions.clear();return;}

    const pos=[];
    const index=new Map();

    nodes.forEach((node,i)=>{
      const id=node.body_id??node.id??i;
      index.set(id,i);
      const prior=this.positions.get(String(id));
      if(prior){pos.push({x:prior.x,y:prior.y});return;}
      const a=hash01(id)*Math.PI*2;
      const r=.18+.25*hash01(String(id)+'r');
      pos.push({x:.5+Math.cos(a)*r,y:.5+Math.sin(a)*r*.72});
    });

    const links=[];
    for(const edge of edges){
      const a=index.get(edge.source),b=index.get(edge.target);
      if(a===undefined||b===undefined||a===b)continue;
      links.push({a,b,w:Math.abs(Number(edge.weight)||0)});
    }

    const n=pos.length;
    const iterations=n>260?24:38;
    for(let step=0;step<iterations;step++){
      const fx=new Float32Array(n),fy=new Float32Array(n);
      for(let i=0;i<n;i++){
        for(let j=i+1;j<n;j++){
          const dx=pos[i].x-pos[j].x,dy=pos[i].y-pos[j].y;
          const d2=dx*dx+dy*dy+.0008;
          const f=.000032/d2;
          fx[i]+=dx*f;fy[i]+=dy*f;fx[j]-=dx*f;fy[j]-=dy*f;
        }
      }
      for(const link of links){
        const p=pos[link.a],q=pos[link.b];
        const dx=q.x-p.x,dy=q.y-p.y;
        const d=Math.sqrt(dx*dx+dy*dy)+1e-5;
        const f=(d-.055)*(.018+Math.min(.03,link.w*.002));
        const ux=dx/d,uy=dy/d;
        fx[link.a]+=ux*f;fy[link.a]+=uy*f;
        fx[link.b]-=ux*f;fy[link.b]-=uy*f;
      }
      for(let i=0;i<n;i++){
        fx[i]+=(.5-pos[i].x)*.006;
        fy[i]+=(.5-pos[i].y)*.008;
        pos[i].x=clamp(pos[i].x+fx[i],.04,.96);
        pos[i].y=clamp(pos[i].y+fy[i],.05,.95);
      }
    }

    nodes.forEach((node,i)=>{
      const id=node.body_id??node.id??i;
      this.positions.set(String(id),pos[i]);
    });
  }

  buildStaticLayer(){
    if(!this.canvas.width||!this.canvas.height)return;
    this.staticLayer.width=this.canvas.width;
    this.staticLayer.height=this.canvas.height;
    const c=this.staticLayer.getContext('2d',{alpha:true});
    c.setTransform(this.dpr||1,0,0,this.dpr||1,0,0);
    const w=this.canvas.width/(this.dpr||1),h=this.canvas.height/(this.dpr||1);
    const area={x:10,y:56,w:w-20,h:h-78};
    const nodes=this.network.nodes||[];
    const edges=this.network.edges||[];

    c.clearRect(0,0,w,h);
    if(!nodes.length)return;

    c.save();
    c.beginPath();c.rect(area.x,area.y,area.w,area.h);c.clip();

    let maxWeight=0;
    for(const edge of edges)maxWeight=Math.max(maxWeight,Math.abs(Number(edge.weight)||0));
    maxWeight=Math.max(maxWeight,1e-5);

    for(const edge of edges){
      const a=this.positions.get(String(edge.source));
      const b=this.positions.get(String(edge.target));
      if(!a||!b)continue;
      const strength=clamp(Math.abs(Number(edge.weight)||0)/maxWeight);
      const color=nodeColor(this.nodeById.get(String(edge.source))||{});
      c.strokeStyle=hexRgba(color,.08+.22*strength);
      c.lineWidth=.35+.65*strength;
      c.beginPath();
      c.moveTo(area.x+a.x*area.w,area.y+a.y*area.h);
      c.lineTo(area.x+b.x*area.w,area.y+b.y*area.h);
      c.stroke();
    }

    for(let i=0;i<nodes.length;i++){
      const id=nodes[i].body_id??nodes[i].id??i;
      const p=this.positions.get(String(id));
      if(!p)continue;
      c.fillStyle=hexRgba(nodeColor(nodes[i]),.38);
      c.beginPath();
      c.arc(area.x+p.x*area.w,area.y+p.y*area.h,.82,0,Math.PI*2);
      c.fill();
    }
    c.restore();
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
    const k=ease(8,dt);
    let active=false;

    const targetBias=this.targetState?.bias||{};
    const keys=new Set([...Object.keys(this.displayBias),...Object.keys(targetBias)]);
    for(const key of keys){
      const target=Number(targetBias[key]);
      if(!Number.isFinite(target))continue;
      const current=Number(this.displayBias[key]);
      const start=Number.isFinite(current)?current:target;
      const next=start+(target-start)*k;
      this.displayBias[key]=next;
      if(Math.abs(next-target)>.01)active=true;
    }

    for(const [key,item] of this.activeVisual){
      item.value+=(item.target-item.value)*k;
      if(Math.abs(item.value-item.target)>.01)active=true;
      if(item.target===0&&item.value<.01)this.activeVisual.delete(key);
    }
    this.pathPulses=this.pathPulses.filter(pulse=>now<pulse.start+pulse.life);
    if(this.pathPulses.length)active=true;

    const hasLiveSpikes=[...this.activeVisual.values()].some(item=>item.value>.015||item.target>.015)
      ||Number(this.targetState?.bias?.active_neurons||0)>0
      ||Number(this.targetState?.bias?.total_spikes||0)>0;

    if(now-this.lastDrawAt>=48){
      this.lastDrawAt=now;
      this.draw(now);
    }

    if(document.hidden){
      this.running=false;
    }else if(active||hasLiveSpikes){
      setTimeout(()=>requestAnimationFrame(this.tick),48);
    }else{
      this.running=false;
      this.draw(now);
    }
  };

  draw(now=performance.now()){
    const c=this.ctx;
    const dpr=this.dpr||1;
    const w=this.canvas.width/dpr,h=this.canvas.height/dpr;
    c.setTransform(dpr,0,0,dpr,0,0);
    c.fillStyle=NEURAL_BG;c.fillRect(0,0,w,h);

    c.fillStyle=CIRCUIT_COLORS.spike;
    c.font='700 10px Consolas,monospace';
    c.fillText('MALECNS v1.0 · LIVE CONNECTOME ACTIVITY',12,18);
    c.font='8px Consolas,monospace';
    c.fillStyle=hexRgba(CIRCUIT_COLORS.groom,.72);
    c.fillText('real simulated spikes + cached directed topology',12,31);

    const bias={...(this.state?.bias||{}),...this.displayBias};
    const active=Number(bias.active_neurons||0);
    const total=Number(bias.total_spikes||0);
    const visual=Number(bias.visual_spikes||0);
    const descending=Number(bias.descending_spikes||0);
    const firing=!!this.state?.ok&&(active>0||total>0||this.activeVisual.size>0);
    c.fillStyle=firing?CIRCUIT_COLORS.giant_fiber:hexRgba(CIRCUIT_COLORS.visual,.58);
    c.fillText(
      `${firing?'LIVE FIRING':'CONNECTED / QUIET'} · ACTIVE ${Math.round(active).toLocaleString()} / 166,700 · SPIKES ${Math.round(total).toLocaleString()} · VIS ${Math.round(visual).toLocaleString()} · DESC ${Math.round(descending).toLocaleString()}`,
      12,46
    );

    if(this.staticLayer.width)c.drawImage(this.staticLayer,0,0,w,h);

    const area={x:10,y:56,w:w-20,h:h-78};
    if(this.network.nodes?.length){
      c.save();c.beginPath();c.rect(area.x,area.y,area.w,area.h);c.clip();
      for(const pulse of this.pathPulses){
        if(now<pulse.start)continue;
        const a=this.positions.get(pulse.source),b=this.positions.get(pulse.target);
        if(!a||!b)continue;
        const t=clamp((now-pulse.start)/pulse.life);
        const x=area.x+(a.x+(b.x-a.x)*t)*area.w;
        const y=area.y+(a.y+(b.y-a.y)*t)*area.h;
        const glow=5+pulse.strength*8;
        const g=c.createRadialGradient(x,y,0,x,y,glow);
        g.addColorStop(0,hexRgba(pulse.color,.92));
        g.addColorStop(1,hexRgba(pulse.color,0));
        c.fillStyle=g;c.beginPath();c.arc(x,y,glow,0,Math.PI*2);c.fill();
        c.fillStyle=pulse.color;c.beginPath();c.arc(x,y,1.3+pulse.strength*1.8,0,Math.PI*2);c.fill();
      }
      for(const [id,item] of this.activeVisual){
        if(item.value<=.01)continue;
        const p=this.positions.get(id);
        if(!p)continue;
        const x=area.x+p.x*area.w,y=area.y+p.y*area.h;
        const pulse=.92+.08*Math.sin(now*.006+hash01(id)*6.28);
        const strength=clamp(item.value*pulse);
        const glow=4+strength*8;
        const color=nodeColor(this.nodeById.get(id)||{});
        const gradient=c.createRadialGradient(x,y,0,x,y,glow);
        gradient.addColorStop(0,hexRgba(color,.46+.48*strength));
        gradient.addColorStop(1,hexRgba(color,0));
        c.fillStyle=gradient;c.beginPath();c.arc(x,y,glow,0,Math.PI*2);c.fill();
        c.fillStyle=color;
        c.beginPath();c.arc(x,y,1.3+strength*2.2,0,Math.PI*2);c.fill();
      }
      c.restore();
    }else{
      c.font='9px Consolas,monospace';
      c.fillStyle=hexRgba(CIRCUIT_COLORS.steering,.72);
      c.fillText(this.state?.ok?'WAITING FOR ACTIVE CONNECTOME TELEMETRY':'MALECNS TELEMETRY OFFLINE',22,76);
    }

    c.font='7px Consolas,monospace';
    c.fillStyle=hexRgba(CIRCUIT_COLORS.visual,.62);
    c.fillText(
      this.network.nodes?.length
        ?`CACHED TOPOLOGY · ${this.network.nodes.length} sampled neurons · ${this.network.edges.length} real edges · dynamic activity overlay`
        :'waiting for real MaleCNS active subnetwork',
      12,h-9
    );
  }
}
