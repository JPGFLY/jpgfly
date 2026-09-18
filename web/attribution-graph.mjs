const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const safe=(v,f=0)=>Number.isFinite(Number(v))?Number(v):f;
const TAU=Math.PI*2;

const SIGNALS=[
  {id:'visual',label:'VISUAL SALIENCE',short:'VISUAL',source:'Z',maxHz:95,group:'sense'},
  {id:'arousal',label:'AROUSAL',short:'AROUSAL',source:'Z',maxHz:105,group:'state'},
  {id:'escape',label:'ESCAPE / GIANT FIBER',short:'ESCAPE',source:'M/Z',maxHz:140,group:'state'},
  {id:'left',label:'STEER LEFT',short:'TURN L',source:'M',maxHz:120,group:'motor'},
  {id:'forward',label:'WALK / FORWARD',short:'FWD',source:'M',maxHz:130,group:'motor'},
  {id:'right',label:'STEER RIGHT',short:'TURN R',source:'M',maxHz:120,group:'motor'},
  {id:'compose',label:'COMPOSITION DRIVE',short:'COMPOSE',source:'D',maxHz:90,group:'decision'},
  {id:'brush',label:'BRUSH PRESSURE',short:'BRUSH',source:'D',maxHz:100,group:'decision'},
  {id:'action',label:'ACTION COMMIT',short:'ACTION',source:'D',maxHz:130,group:'decision'},
];

const COLORS={
  sense:[87,224,230],
  state:[255,61,174],
  motor:[117,231,170],
  decision:[255,190,86],
};

function signalState(spec){return{...spec,rate:0,target:0,energy:0,history:Array(64).fill(0),lastValue:''};}

export class BrainActivityView{
  constructor(canvas,status){
    this.canvas=canvas;
    this.ctx=canvas.getContext('2d',{alpha:false});
    this.status=status;
    this.signals=SIGNALS.map(signalState);
    this.running=false;
    this.lastFrame=performance.now();
    this.lastSample=0;
    this.lastDrawAt=0;
    this.pulses=[];
    this.decisionLabel='WAITING';
    this.provider='';
    this.visible=true;
    this.dpr=1;
    this.resize();

    if('IntersectionObserver' in window){
      this.visible=false;
      this.visibilityObserver=new IntersectionObserver(entries=>{
        const entry=entries[0];
        this.visible=Boolean(entry?.isIntersecting);
        if(this.visible){
          this.resize();
          this.schedule();
        }else{
          this.running=false;
        }
      },{rootMargin:'180px 0px',threshold:0});
      this.visibilityObserver.observe(this.canvas);
    }

    document.addEventListener('visibilitychange',()=>{
      if(document.hidden){
        this.running=false;
      }else if(this.visible){
        this.resize();
        this.schedule();
      }
    },{passive:true});
  }

  get(id){return this.signals.find(s=>s.id===id)}

  resize(){
    const box=this.canvas.getBoundingClientRect();
    const dpr=Math.min(1.25,window.devicePixelRatio||1);
    const width=Math.max(1,Math.round(box.width*dpr));
    const height=Math.max(1,Math.round(box.height*dpr));
    const changed=this.canvas.width!==width||this.canvas.height!==height||this.dpr!==dpr;
    this.dpr=dpr;
    if(changed){
      this.canvas.width=width;
      this.canvas.height=height;
      this.ctx.setTransform(dpr,0,0,dpr,0,0);
    }
    if(this.visible&&!document.hidden)this.draw(performance.now());
  }

  set(id,value,label=''){
    const s=this.get(id);
    if(!s)return;
    s.target=Math.max(s.target,clamp(value));
    s.energy=Math.max(s.energy,.28+clamp(value)*.72);
    if(label)s.lastValue=String(label).slice(0,24);
  }

  pushDecision(record){
    const a=record?.action||record||{},o=record?.observation_summary||{},z=a.zebracnsActivity||{},zs=z.signals||{},m=a.malecnsActivity||{};
    const occ=clamp(safe(o.canvasOccupancy,.25)),contrast=clamp(safe(o.densityContrast,.25)),rep=clamp(safe(o.repetition,.15)),change=clamp(safe(o.meaningfulChangeRate,.5));
    const pressure=clamp(safe(a.pressure,.5)),confidence=clamp(safe(a.confidence,.55)),explore=clamp(safe(a.exploration,.5));
    const hasZ=Object.keys(zs).length>0,hasM=Object.keys(m).length>0;
    const visual=clamp(safe(zs.visual_salience,Math.max(contrast,occ*.72)));
    const arousal=clamp(safe(zs.arousal,.20+contrast*.58+explore*.12));
    const escape=clamp(Math.max(
      safe(zs.escape_drive,0),
      safe(zs.state_instability,0)*.75,
      Math.abs(safe(m.escape_drive??m.jump_signal??m.jump,0))>1?Math.abs(safe(m.escape_drive??m.jump_signal??m.jump,0))/120:Math.abs(safe(m.escape_drive??m.jump_signal??m.jump,0))
    ));
    const turn=safe(m.turn_signal??m.turn_bias,0);
    const norm=v=>clamp(Math.abs(safe(v,0))>1?Math.abs(safe(v,0))/120:Math.abs(safe(v,0)));
    const left=norm(m.motor_left??(turn<0?Math.abs(turn):0));
    const right=norm(m.motor_right??(turn>0?Math.abs(turn):0));
    const forward=norm(m.forward_signal??m.forward_drive??(.2+change*.58));
    const compose=clamp(.22+confidence*.58+(a.contextPass==='INTEGRATE'?.12:0)+(a.contextPass==='EDIT_RESOLVE'?.08:0));
    const brush=clamp(.15+pressure*.78);
    const action=a.intent==='FINISH_ARTWORK'?1:clamp(.34+change*.50+rep*.08);

    this.set('visual',visual,hasZ?'ZEBRACNS':'CANVAS');
    this.set('arousal',arousal,hasZ?'ZEBRACNS':'DERIVED');
    this.set('escape',escape,escape>.55?'FIRING':'QUIET');
    this.set('left',left,hasM?'MALECNS':'DERIVED');
    this.set('forward',forward,hasM?'MALECNS':'DERIVED');
    this.set('right',right,hasM?'MALECNS':'DERIVED');
    this.set('compose',compose,a.decisionMode||a.compositionPass||'BUILD');
    this.set('brush',brush,a.brushTool||'TOOL');
    this.set('action',action,a.intent||'MOVE');
    this.decisionLabel=`${String(a.intent||'MOVE').toUpperCase()} · ${String(a.phase||a.contextPass||'').toUpperCase()}`;

    const now=performance.now();
    const order=['visual','arousal','escape','left','forward','right','compose','brush','action'];
    order.forEach((id,index)=>{
      const s=this.get(id);
      if(s&&s.target>.30)this.pulses.push({id,start:now+index*28,life:460+index*16});
    });
    this.pulses=this.pulses.slice(-90);
    if(this.status)this.status.textContent=`LIVE FIRING / ${hasM?'MALECNS + ':''}${hasZ?'ZEBRACNS + ':''}RECORDED DECISION / ${this.decisionLabel}`;
    this.schedule();
  }

  signal(cluster,payload={}){
    const map={perception:'visual',memory:'compose',evaluation:'compose',planning:'compose',action:'action',completion:'action'};
    const id=map[cluster]||'compose';
    this.set(id,.72,payload.phase||payload.movementStyle||cluster);
    this.schedule();
  }

  setLanguageState(state={}){this.provider=String(state.provider||state.source||this.provider||'');}
  pushComment(comment={}){this.provider=String(comment.provider||this.provider||'VOICE');this.set('compose',.45,'VOICE');this.schedule();}
  sample(){for(const s of this.signals){s.history.push(clamp(s.rate));if(s.history.length>64)s.history.shift();}}

  schedule(){
    if(this.running||document.hidden||!this.visible)return;
    this.running=true;
    this.lastFrame=performance.now();
    this.lastSample=this.lastFrame;
    requestAnimationFrame(this.tick);
  }

  tick=(now)=>{
    if(document.hidden||!this.visible){
      this.running=false;
      return;
    }
    const dt=Math.min(.05,Math.max(.001,(now-this.lastFrame)/1000));
    this.lastFrame=now;
    let active=false;
    for(const s of this.signals){
      const ease=1-Math.exp(-9*dt);
      s.rate+=(s.target-s.rate)*ease;
      s.target*=Math.exp(-1.45*dt);
      s.energy*=Math.exp(-1.25*dt);
      if(s.rate>.004||s.target>.004||s.energy>.01)active=true;
    }
    if(now-this.lastSample>95){this.sample();this.lastSample=now;}
    this.pulses=this.pulses.filter(p=>now<p.start+p.life);
    if(this.pulses.length)active=true;

    if(now-this.lastDrawAt>=42||!this.lastDrawAt){
      this.lastDrawAt=now;
      this.draw(now);
    }

    if(active){
      requestAnimationFrame(this.tick);
    }else{
      this.running=false;
      this.draw(now);
    }
  };

  draw(now){
    const c=this.ctx,dpr=this.dpr||1,w=this.canvas.width/dpr,h=this.canvas.height/dpr;
    c.setTransform(dpr,0,0,dpr,0,0);
    c.fillStyle='#020203';c.fillRect(0,0,w,h);
    const left=18,labelW=Math.min(185,w*.25),rateW=Math.min(72,w*.10),graphX=left+labelW+rateW,graphW=Math.max(120,w-graphX-18);
    const top=35,bottom=30,rowH=(h-top-bottom)/this.signals.length;

    c.font='700 8px Consolas,monospace';c.fillStyle='rgba(255,255,255,.72)';c.fillText('JPGFLY / LIVE NEURAL FIRING',left,16);
    c.textAlign='right';c.fillStyle='rgba(255,255,255,.38)';c.fillText('M MALECNS · Z ZEBRACNS · D DERIVED DECISION SIGNAL',w-16,16);c.textAlign='left';

    for(let i=0;i<this.signals.length;i++){
      const s=this.signals[i],y=top+i*rowH,cy=y+rowH*.52,[r,g,b]=COLORS[s.group]||[200,200,200];
      c.strokeStyle='rgba(255,255,255,.055)';c.lineWidth=1;c.beginPath();c.moveTo(left,y+rowH);c.lineTo(w-16,y+rowH);c.stroke();
      c.font='700 7px Consolas,monospace';c.fillStyle='rgba(255,255,255,.78)';c.fillText(s.label,left,cy-2);
      c.font='6px Consolas,monospace';c.fillStyle='rgba(255,255,255,.34)';c.fillText(`${s.source}${s.lastValue?' · '+s.lastValue:''}`,left,cy+8);
      c.textAlign='right';c.font='700 8px Consolas,monospace';c.fillStyle=`rgba(${r},${g},${b},.82)`;c.fillText(`${Math.round(s.rate*s.maxHz)} Hz`,graphX-10,cy+2);c.textAlign='left';

      c.strokeStyle='rgba(255,255,255,.05)';c.beginPath();c.moveTo(graphX,cy);c.lineTo(graphX+graphW,cy);c.stroke();
      for(let tick=0;tick<=4;tick++){
        const x=graphX+graphW*tick/4;
        c.strokeStyle='rgba(255,255,255,.025)';c.beginPath();c.moveTo(x,y+3);c.lineTo(x,y+rowH-3);c.stroke();
      }

      const hist=s.history,cxStep=graphW/Math.max(1,hist.length-1),amp=rowH*.32;
      c.strokeStyle=`rgba(${r},${g},${b},${.34+s.energy*.55})`;c.lineWidth=.8+s.energy*.85;c.beginPath();
      hist.forEach((v,j)=>{
        const x=graphX+j*cxStep,yy=cy-clamp(v)*amp+(Math.sin(j*.73+i)*.35);
        if(j===0)c.moveTo(x,yy);else c.lineTo(x,yy);
      });
      c.stroke();
      const liveX=graphX+graphW,liveY=cy-s.rate*amp;
      c.fillStyle=`rgba(${r},${g},${b},${.45+s.energy*.5})`;
      c.beginPath();c.arc(liveX,liveY,1.8+s.energy*2.5,0,TAU);c.fill();
    }

    for(const p of this.pulses){
      const s=this.get(p.id);
      if(!s||now<p.start)continue;
      const i=this.signals.indexOf(s),t=clamp((now-p.start)/p.life),y=top+i*rowH+rowH*.52,x=graphX+graphW*t,[r,g,b]=COLORS[s.group]||[255,255,255];
      c.shadowColor=`rgb(${r},${g},${b})`;c.shadowBlur=7;c.fillStyle=`rgba(${r},${g},${b},${.75*(1-t)})`;c.beginPath();c.arc(x,y,1.2+2*(1-t),0,TAU);c.fill();c.shadowBlur=0;
    }

    c.fillStyle='rgba(255,255,255,.34)';c.font='6px Consolas,monospace';c.fillText('~6 s HISTORY',graphX,h-9);
    c.textAlign='right';c.fillText(`${this.decisionLabel}${this.provider?' · VOICE '+this.provider:''}`,w-16,h-9);c.textAlign='left';
  }
}
