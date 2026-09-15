const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));

function node(id,label,x,y){return{id,label,x,y,value:'',energy:0}}
const BASE=[
  node('canvas','CANVAS',.08,.30),
  node('memory','MEMORY',.08,.70),
  node('phase','PHASE',.30,.18),
  node('critic','CRITIC',.30,.46),
  node('motif','MOTIF',.30,.76),
  node('brush','BRUSH',.56,.22),
  node('scale','SCALE',.56,.50),
  node('motion','MOTION',.56,.78),
  node('action','ACTION',.84,.50),
];
const LINKS=[
  ['canvas','phase'],['canvas','critic'],['memory','motif'],
  ['phase','brush'],['critic','scale'],['motif','motion'],
  ['brush','action'],['scale','action'],['motion','action'],
];

export class BrainActivityView{
  constructor(canvas,status){
    this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false});this.status=status;
    this.nodes=BASE.map(x=>({...x}));this.edges=[];this.history=[];this.language={};
    this.running=false;this.resize();
  }
  resize(){
    const box=this.canvas.getBoundingClientRect();
    this.canvas.width=Math.max(1,Math.round(box.width));this.canvas.height=Math.max(1,Math.round(box.height));
    this.draw(performance.now());
  }
  get(id){return this.nodes.find(n=>n.id===id)}
  edge(a,b,w=.5){this.edges.push({a,b,w:clamp(w),born:performance.now()});this.edges=this.edges.slice(-18)}
  excite(id,w=.7,value=''){
    const n=this.get(id);if(!n)return;n.energy=Math.max(n.energy,clamp(w));if(value!==undefined)n.value=String(value||'');
  }
  pushDecision(record){
    const a=record?.action||record||{};const o=record?.observation_summary||{};
    const mem=Array.isArray(a.memoryContext)?a.memoryContext:[];
    const confidence=clamp(Number(a.confidence??.5));
    const exploration=clamp(Number(a.exploration??.5));
    const pressure=clamp(Number(a.pressure??.5));
    const readiness=clamp(Number(a?.evaluation?.readiness??a?.evaluation?.compositionScore??.5));
    const occupancy=clamp(Number(o.canvasOccupancy??.5));
    const contrast=clamp(Number(o.densityContrast??.5));

    this.excite('canvas',.45+occupancy*.5,'occ '+occupancy.toFixed(2));
    this.excite('memory',mem.length?.85:.18,mem.slice(0,2).join(' + ')||'none');
    this.excite('phase',.72,a.compositionPass||a.phase||'OBSERVE');
    this.excite('critic',.45+readiness*.5,'score '+readiness.toFixed(2));
    this.excite('motif',a.motifHint&&a.motifHint!=='NONE'?.82:.30,a.motifHint||'NONE');
    this.excite('brush',.60+pressure*.35,a.brushTool||'tool');
    this.excite('scale',.55+Math.abs(Number(a.scale||1)-1)*.3,'x'+Number(a.scale||1).toFixed(2));
    this.excite('motion',.55+exploration*.35,a.movementStyle||'MOVE');
    this.excite('action',.70+confidence*.28,a.intent||'MOVE');

    this.edges=[];
    this.edge('canvas','phase',.45+occupancy*.45);
    this.edge('canvas','critic',.40+contrast*.45);
    this.edge('memory','motif',mem.length?Math.min(1,.45+mem.length*.12):.12);
    this.edge('phase','brush',.45+confidence*.35);
    this.edge('critic','scale',.35+readiness*.50);
    this.edge('motif','motion',a.motifHint&&a.motifHint!=='NONE'?.78:.30);
    this.edge('brush','action',.50+pressure*.45);
    this.edge('scale','action',.48+Math.min(.45,Math.abs(Number(a.scale||1)-1)*.30));
    this.edge('motion','action',.45+exploration*.40);

    this.history.push({at:performance.now(),action:a});
    this.history=this.history.slice(-32);
    if(this.status)this.status.textContent='ATTRIBUTION / '+(a.compositionPass||a.phase||'OBS')+' -> '+(a.intent||'MOVE')+' / '+(a.movementStyle||'motion');
    this.schedule();
  }
  signal(){this.schedule()}
  setLanguageState(state={}){this.language={...this.language,...state}}
  pushComment(){this.schedule()}
  schedule(){
    if(this.running)return;this.running=true;
    const tick=now=>{
      let active=false;
      for(const n of this.nodes){n.energy*=.94;if(n.energy>.03)active=true}
      this.draw(now);
      if(active)requestAnimationFrame(tick);else this.running=false;
    };
    requestAnimationFrame(tick);
  }
  draw(now){
    const c=this.ctx,w=this.canvas.width,h=this.canvas.height;
    c.fillStyle='#000';c.fillRect(0,0,w,h);
    c.font='8px Consolas,monospace';c.fillStyle='rgba(255,255,255,.35)';
    c.fillText('JPGFLY / LIVE ATTRIBUTION GRAPH',12,16);
    c.textAlign='right';c.fillText('RECORDED DECISION TELEMETRY',w-12,16);c.textAlign='left';

    for(const [a,b] of LINKS){
      const edge=this.edges.find(e=>e.a===a&&e.b===b);
      const na=this.get(a),nb=this.get(b),weight=edge?.w??.08;
      c.strokeStyle='rgba(255,255,255,'+(.04+weight*.62)+')';
      c.lineWidth=.5+weight*3.2;
      c.beginPath();c.moveTo(na.x*w,na.y*h);c.lineTo(nb.x*w,nb.y*h);c.stroke();
    }

    for(const n of this.nodes){
      const x=n.x*w,y=n.y*h,r=8+n.energy*8;
      c.fillStyle='rgba(255,255,255,'+(.06+n.energy*.34)+')';
      c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();
      c.strokeStyle='rgba(255,255,255,'+(.28+n.energy*.66)+')';c.lineWidth=1+n.energy*1.5;c.stroke();
      c.textAlign='center';c.font='700 9px Consolas,monospace';c.fillStyle='rgba(255,255,255,.9)';c.fillText(n.label,x,y-r-7);
      c.font='7px Consolas,monospace';c.fillStyle='rgba(255,255,255,.48)';c.fillText((n.value||'').slice(0,22),x,y+r+12);
    }
    c.textAlign='left';c.font='7px Consolas,monospace';c.fillStyle='rgba(255,255,255,.28)';
    c.fillText('EDGE WIDTH = RELATIVE INFLUENCE FROM RECORDED FLY STATE',12,h-10);
  }
}