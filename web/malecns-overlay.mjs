const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)||0));

function hash01(value){
  let h=2166136261>>>0;
  const s=String(value??'');
  for(let i=0;i<s.length;i++){
    h^=s.charCodeAt(i);
    h=Math.imul(h,16777619)>>>0;
  }
  return h/4294967295;
}

export class MaleCNSOverlay{
  constructor(canvas){
    this.canvas=canvas;
    this.ctx=canvas.getContext('2d',{alpha:true});
    this.state={ok:false,top_active:[],bias:{}};
    this.network={ok:false,nodes:[],edges:[]};
    this.positions=new Map();
    this.resize();
  }

  resize(){
    const box=this.canvas.getBoundingClientRect();
    const dpr=Math.min(2,window.devicePixelRatio||1);
    this.canvas.width=Math.max(1,Math.round(box.width*dpr));
    this.canvas.height=Math.max(1,Math.round(box.height*dpr));
    this.ctx.setTransform(dpr,0,0,dpr,0,0);
    this.draw();
  }

  setNetwork(data={}){
    this.network={
      ok:!!data?.ok,
      nodes:Array.isArray(data?.nodes)?data.nodes:[],
      edges:Array.isArray(data?.edges)?data.edges:[],
      telemetry_schema:data?.telemetry_schema||'',
    };
    this.layoutNetwork();
    this.draw();
  }

  pushState(state={}){
    this.state=state&&typeof state==='object'?state:{ok:false,top_active:[],bias:{}};
    this.draw();
  }

  pushActivity(activity={}){
    this.state={
      ...this.state,
      ok:true,
      bias:{...(this.state.bias||{}),...(activity||{})},
    };
    this.draw();
  }

  layoutNetwork(){
    const nodes=this.network.nodes||[];
    const edges=this.network.edges||[];
    if(!nodes.length)return;

    const pos=[];
    const index=new Map();

    nodes.forEach((node,i)=>{
      index.set(node.body_id,i);
      const prior=this.positions.get(node.body_id);
      if(prior){
        pos.push({x:prior.x,y:prior.y});
        return;
      }
      const a=hash01(node.body_id)*Math.PI*2;
      const r=.18+.25*hash01(String(node.body_id)+'r');
      pos.push({
        x:.5+Math.cos(a)*r,
        y:.5+Math.sin(a)*r*.72,
      });
    });

    const links=[];
    for(const edge of edges){
      const a=index.get(edge.source),b=index.get(edge.target);
      if(a===undefined||b===undefined||a===b)continue;
      links.push({a,b,w:Math.abs(Number(edge.weight)||0)});
    }

    const n=pos.length;
    const iterations=n>260?38:56;

    for(let step=0;step<iterations;step++){
      const fx=new Float32Array(n);
      const fy=new Float32Array(n);

      // Repulsion gives the connected graph volume instead of collapsing
      // everything into a knot.
      for(let i=0;i<n;i++){
        for(let j=i+1;j<n;j++){
          let dx=pos[i].x-pos[j].x;
          let dy=pos[i].y-pos[j].y;
          let d2=dx*dx+dy*dy+.0008;
          const f=.000032/d2;
          fx[i]+=dx*f;fy[i]+=dy*f;
          fx[j]-=dx*f;fy[j]-=dy*f;
        }
      }

      // Real MaleCNS directed edges become springs. Layout is derived from
      // connectivity, not claimed anatomical placement.
      for(const link of links){
        const p=pos[link.a],q=pos[link.b];
        const dx=q.x-p.x,dy=q.y-p.y;
        const d=Math.sqrt(dx*dx+dy*dy)+1e-5;
        const target=.055;
        const strength=.018+Math.min(.03,link.w*.002);
        const f=(d-target)*strength;
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

    nodes.forEach((node,i)=>this.positions.set(node.body_id,pos[i]));
  }

  draw(){
    const c=this.ctx;
    const dpr=Math.min(2,window.devicePixelRatio||1);
    const w=this.canvas.width/dpr,h=this.canvas.height/dpr;
    c.clearRect(0,0,w,h);
    c.fillStyle='#050505';
    c.fillRect(0,0,w,h);

    const state=this.state||{};
    const bias=state.bias||{};
    const nodes=this.network.nodes||[];
    const edges=this.network.edges||[];
    const nodeById=new Map(nodes.map(node=>[node.body_id,node]));

    c.fillStyle='rgba(255,255,255,.96)';
    c.font='700 10px Consolas,monospace';
    c.fillText('MALECNS v1.0 · LIVE CONNECTOME ACTIVITY',12,18);
    c.font='8px Consolas,monospace';
    c.fillStyle='rgba(255,255,255,.52)';
    c.fillText('real simulated spikes + real directed MaleCNS edges',12,31);

    const active=Number(bias.active_neurons||0);
    const total=Number(bias.total_spikes||0);
    const visual=Number(bias.visual_spikes||0);
    const descending=Number(bias.descending_spikes||0);

    c.fillStyle='rgba(255,255,255,.74)';
    c.fillText(
      `ACTIVE ${active.toLocaleString()} / 166,700 · SPIKES ${total.toLocaleString()} · VIS ${visual.toLocaleString()} · DESC ${descending.toLocaleString()}`,
      12,46
    );

    const area={x:10,y:56,w:w-20,h:h-78};
    c.save();
    c.beginPath();
    c.rect(area.x,area.y,area.w,area.h);
    c.clip();

    if(nodes.length){
      let maxWeight=0;
      for(const edge of edges)maxWeight=Math.max(maxWeight,Math.abs(Number(edge.weight)||0));
      maxWeight=Math.max(maxWeight,1e-5);

      // Real directed synaptic connections.
      for(const edge of edges){
        const a=this.positions.get(edge.source);
        const b=this.positions.get(edge.target);
        if(!a||!b)continue;
        const strength=clamp(Math.abs(Number(edge.weight)||0)/maxWeight);
        c.strokeStyle=`rgba(255,255,255,${.035+.11*strength})`;
        c.lineWidth=.35+.65*strength;
        c.beginPath();
        c.moveTo(area.x+a.x*area.w,area.y+a.y*area.h);
        c.lineTo(area.x+b.x*area.w,area.y+b.y*area.h);
        c.stroke();
      }

      const maxSpikes=Math.max(1,...nodes.map(node=>Number(node.spikes)||0));

      // Real sampled nodes; live-spiking ones glow.
      for(const node of nodes){
        const p=this.positions.get(node.body_id);
        if(!p)continue;
        const x=area.x+p.x*area.w;
        const y=area.y+p.y*area.h;
        const spikes=Number(node.spikes)||0;
        const activeNow=spikes>0;
        const strength=clamp(spikes/maxSpikes);

        if(activeNow){
          const glow=5+strength*10;
          const gradient=c.createRadialGradient(x,y,0,x,y,glow);
          gradient.addColorStop(0,`rgba(255,255,255,${.60+.38*strength})`);
          gradient.addColorStop(1,'rgba(255,255,255,0)');
          c.fillStyle=gradient;
          c.beginPath();c.arc(x,y,glow,0,Math.PI*2);c.fill();
        }

        c.fillStyle=activeNow
          ? `rgba(255,255,255,${.68+.32*strength})`
          : 'rgba(255,255,255,.18)';
        c.beginPath();
        c.arc(x,y,activeNow?1.7+strength*2.6:.85,0,Math.PI*2);
        c.fill();
      }
    }else{
      c.font='9px Consolas,monospace';
      c.fillStyle='rgba(255,255,255,.42)';
      c.fillText(
        state.ok?'WAITING FOR ACTIVE CONNECTOME TELEMETRY':'MALECNS TELEMETRY OFFLINE',
        area.x+12,area.y+20
      );
    }
    c.restore();

    c.font='7px Consolas,monospace';
    c.fillStyle='rgba(255,255,255,.45)';
    c.fillText(
      nodes.length
        ? `LIVE SUBNETWORK ${nodes.length} neurons · ${edges.length} real edges · topology layout (not anatomy)`
        : 'waiting for real MaleCNS active subnetwork',
      12,h-9
    );
  }
}
