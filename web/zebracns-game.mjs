const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)||0));
const ease=(rate,dt)=>1-Math.exp(-rate*Math.max(0,dt));

export class ZebraCNSGame{
  constructor(canvas,statusNode){
    this.canvas=canvas;
    this.statusNode=statusNode;
    this.ctx=canvas.getContext('2d',{alpha:false});
    this.state={
      ok:true,enabled:false,connected:false,status:'BACKBONE_ONLY',
      connectome_loaded:false,activity_loaded:false,biological_data_loaded:false,action:'NONE',
      game:{fish:[.42,.55],food:[.80,.25],predator:[.18,.74],score:0,episode:0},
      signals:{},nodes:[]
    };
    this.targetState=this.state;
    this.displayGame={
      fish:[.42,.55],food:[.80,.25],predator:[.18,.74]
    };
    this.displaySignals={};
    this.nodeVisual=new Map();
    this.running=false;
    this.lastFrame=performance.now();
    this.resize();
  }

  pushState(state={}){
    if(!(state&&typeof state==='object'))return;
    this.targetState=state;
    this.state={...this.state,...state};
    const game=state.game||{};
    for(const key of ['fish','food','predator']){
      if(Array.isArray(game[key])&&game[key].length>=2){
        if(!Array.isArray(this.displayGame[key]))this.displayGame[key]=[...game[key]];
      }
    }

    const seen=new Set();
    for(const node of (Array.isArray(state.nodes)?state.nodes:[])){
      const id=String(node.id??node.neuron_id??`${node.x}:${node.y}`);
      seen.add(id);
      const existing=this.nodeVisual.get(id)||{
        x:clamp(node.x),y:clamp(node.y),activity:0,
        targetX:clamp(node.x),targetY:clamp(node.y),targetActivity:0
      };
      existing.targetX=clamp(node.x);
      existing.targetY=clamp(node.y);
      existing.targetActivity=clamp(node.activity);
      this.nodeVisual.set(id,existing);
    }
    for(const [id,node] of this.nodeVisual){
      if(!seen.has(id))node.targetActivity=0;
    }

    this.syncStatus();
    this.schedule();
  }

  syncStatus(){
    if(!this.statusNode)return;
    const s=this.state||{};
    const loaded=!!(s.biological_data_loaded||s.activity_loaded||s.connectome_loaded);
    if(s.connected&&loaded){
      this.statusNode.textContent=`LIVE · ${s.dataset||'LOCAL BIOLOGICAL DATA'} · ACTION ${s.action||'NONE'}`;
    }else if(s.enabled&&s.status==='LOCAL_ENGINE_OFFLINE'){
      this.statusNode.textContent='LOCAL ENGINE OFFLINE · START ZEBRACNS ON THIS MACHINE';
    }else if(s.enabled&&s.connected){
      this.statusNode.textContent='LOCAL ENGINE ONLINE · REAL ACTIVITY DATA NOT LOADED';
    }else{
      this.statusNode.textContent='BACKBONE READY · REAL ACTIVITY DATA NOT LOADED';
    }
  }

  resize(){
    const box=this.canvas.getBoundingClientRect();
    this.dpr=Math.min(1.5,window.devicePixelRatio||1);
    this.canvas.width=Math.max(1,Math.round(box.width*this.dpr));
    this.canvas.height=Math.max(1,Math.round(Math.max(300,box.height)*this.dpr));
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
    const fast=ease(8,dt);
    const slow=ease(5,dt);
    let active=false;

    const targetGame=this.targetState?.game||{};
    for(const key of ['fish','food','predator']){
      const target=Array.isArray(targetGame[key])?targetGame[key]:this.displayGame[key];
      for(let i=0;i<2;i++){
        const t=clamp(target?.[i]??this.displayGame[key][i]);
        const n=this.displayGame[key][i]+(t-this.displayGame[key][i])*slow;
        if(Math.abs(n-t)>.0008)active=true;
        this.displayGame[key][i]=n;
      }
    }

    const targetSignals=this.targetState?.signals||{};
    const keys=new Set([...Object.keys(this.displaySignals),...Object.keys(targetSignals)]);
    for(const key of keys){
      const t=clamp(targetSignals[key]);
      const current=Number.isFinite(this.displaySignals[key])?this.displaySignals[key]:t;
      const n=current+(t-current)*slow;
      this.displaySignals[key]=n;
      if(Math.abs(n-t)>.002)active=true;
    }

    for(const [id,node] of this.nodeVisual){
      node.x+=(node.targetX-node.x)*fast;
      node.y+=(node.targetY-node.y)*fast;
      node.activity+=(node.targetActivity-node.activity)*fast;
      if(Math.abs(node.activity-node.targetActivity)>.01)active=true;
      if(node.targetActivity===0&&node.activity<.01)this.nodeVisual.delete(id);
    }

    this.draw(now);
    if(active)requestAnimationFrame(this.tick);
    else this.running=false;
  };

  line(x1,y1,x2,y2,alpha=.3,width=1){
    const c=this.ctx;
    c.strokeStyle=`rgba(255,255,255,${alpha})`;
    c.lineWidth=width;
    c.beginPath();c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();
  }

  label(text,x,y,alpha=.55,size=8){
    const c=this.ctx;
    c.fillStyle=`rgba(255,255,255,${alpha})`;
    c.font=`${size}px Consolas,monospace`;
    c.fillText(text,x,y);
  }

  drawFish(x,y,scale=1,now=0){
    const c=this.ctx;
    c.save();
    c.translate(x,y+Math.sin(now*.004)*.8);
    c.scale(scale,scale);
    c.strokeStyle='rgba(255,255,255,.92)';
    c.fillStyle='rgba(255,255,255,.10)';
    c.lineWidth=1.5;
    c.beginPath();c.ellipse(0,0,17,8,0,0,Math.PI*2);c.fill();c.stroke();
    c.beginPath();c.moveTo(-16,0);c.lineTo(-29,-10);c.lineTo(-27,10);c.closePath();c.fill();c.stroke();
    c.beginPath();c.arc(10,-2,1.5,0,Math.PI*2);c.fillStyle='#fff';c.fill();
    c.restore();
  }

  drawTank(area,now){
    const c=this.ctx;
    const s=this.state||{};
    const game=s.game||{};
    const fish=this.displayGame.fish;
    const food=this.displayGame.food;
    const predator=this.displayGame.predator;

    c.strokeStyle='rgba(255,255,255,.26)';
    c.strokeRect(area.x,area.y,area.w,area.h);

    for(let i=1;i<5;i++)this.line(area.x+i*area.w/5,area.y,area.x+i*area.w/5,area.y+area.h,.035);
    for(let i=1;i<4;i++)this.line(area.x,area.y+i*area.h/4,area.x+area.w,area.y+i*area.h/4,.035);

    const fx=area.x+clamp(fish[0])*area.w,fy=area.y+clamp(fish[1])*area.h;
    const foodX=area.x+clamp(food[0])*area.w,foodY=area.y+clamp(food[1])*area.h;
    const predX=area.x+clamp(predator[0])*area.w,predY=area.y+clamp(predator[1])*area.h;

    this.drawFish(fx,fy,1,now);
    c.strokeStyle='rgba(255,255,255,.82)';c.lineWidth=1;
    c.beginPath();c.arc(foodX,foodY,5,0,Math.PI*2);c.stroke();
    this.label('FOOD',foodX+9,foodY+3,.5,7);

    this.line(predX-7,predY-7,predX+7,predY+7,.8,1.4);
    this.line(predX+7,predY-7,predX-7,predY+7,.8,1.4);
    this.label('PREDATOR',predX+11,predY+3,.5,7);

    this.label(`SCORE ${Number(game.score||0)}  EPISODE ${Number(game.episode||0)}`,area.x+8,area.y+16,.65,8);
    const loaded=!!(s.biological_data_loaded||s.activity_loaded||s.connectome_loaded);
    this.label(`ACTION ${String(s.action||'NONE').toUpperCase()}`,area.x+8,area.y+30,loaded?.86:.35,8);

    if(!loaded){
      c.fillStyle='rgba(0,0,0,.64)';
      c.fillRect(area.x+1,area.y+area.h-39,area.w-2,38);
      this.label('ENVIRONMENT PREVIEW · CONTROL DISABLED UNTIL REAL ACTIVITY DATA IS LOADED',area.x+9,area.y+area.h-16,.67,8);
    }
  }

  drawBrain(area,now){
    const c=this.ctx;
    const s=this.state||{};
    const live=!!(s.biological_data_loaded||s.activity_loaded||s.connectome_loaded)&&this.nodeVisual.size>0;

    c.strokeStyle='rgba(255,255,255,.32)';
    c.lineWidth=1;
    c.beginPath();
    c.moveTo(area.x+area.w*.50,area.y+area.h*.10);
    c.bezierCurveTo(area.x+area.w*.22,area.y+area.h*.08,area.x+area.w*.13,area.y+area.h*.35,area.x+area.w*.24,area.y+area.h*.56);
    c.bezierCurveTo(area.x+area.w*.34,area.y+area.h*.74,area.x+area.w*.43,area.y+area.h*.78,area.x+area.w*.50,area.y+area.h*.91);
    c.bezierCurveTo(area.x+area.w*.57,area.y+area.h*.78,area.x+area.w*.66,area.y+area.h*.74,area.x+area.w*.76,area.y+area.h*.56);
    c.bezierCurveTo(area.x+area.w*.87,area.y+area.h*.35,area.x+area.w*.78,area.y+area.h*.08,area.x+area.w*.50,area.y+area.h*.10);
    c.stroke();

    if(live){
      let shown=0;
      for(const [id,node] of this.nodeVisual){
        const a=clamp(node.activity);
        if(a<.01)continue;
        shown++;
        const x=area.x+clamp(node.x)*area.w;
        const y=area.y+clamp(node.y)*area.h;
        const pulse=.93+.07*Math.sin(now*.006+shown*.73);
        const value=clamp(a*pulse);
        if(value>.05){
          const g=c.createRadialGradient(x,y,0,x,y,2.5+value*6);
          g.addColorStop(0,`rgba(255,255,255,${.35+value*.48})`);
          g.addColorStop(1,'rgba(255,255,255,0)');
          c.fillStyle=g;c.beginPath();c.arc(x,y,2.5+value*6,0,Math.PI*2);c.fill();
        }
        c.fillStyle=`rgba(255,255,255,${.16+value*.76})`;
        c.beginPath();c.arc(x,y,.7+value*1.9,0,Math.PI*2);c.fill();
      }
      this.label(`REAL ACTIVITY SAMPLE · ${shown} DISPLAYED NEURONS`,area.x+5,area.y+area.h-5,.66,7);
    }else{
      this.label('SCHEMATIC SHELL',area.x+area.w*.32,area.y+area.h*.46,.34,8);
      this.label('NO REAL ACTIVITY DATA',area.x+area.w*.25,area.y+area.h*.52,.62,8);
    }
  }

  gauge(name,value,x,y,w){
    const c=this.ctx;
    const v=clamp(value);
    this.label(name,x,y,.50,7);
    c.strokeStyle='rgba(255,255,255,.16)';c.strokeRect(x,y+5,w,5);
    if(v>0){
      c.fillStyle=`rgba(255,255,255,${.30+v*.65})`;
      c.fillRect(x+1,y+6,Math.max(0,(w-2)*v),3);
    }
  }

  draw(now=performance.now()){
    const c=this.ctx;
    const dpr=this.dpr||1;
    const w=this.canvas.width/dpr,h=this.canvas.height/dpr;
    c.setTransform(dpr,0,0,dpr,0,0);
    c.fillStyle='#050505';c.fillRect(0,0,w,h);

    this.label('ZEBRACNS // ESCAPE TANK',12,18,.96,10);
    this.label('local-first vertebrate circuit game',12,31,.48,8);

    const connected=!!this.state?.connected;
    const loaded=!!(this.state?.biological_data_loaded||this.state?.activity_loaded||this.state?.connectome_loaded);
    const status=loaded?'BIOLOGICAL ACTIVITY ACTIVE':connected?'ENGINE ONLINE / DATA PENDING':'BACKBONE / DORMANT';
    this.label(status,w-190,18,loaded?.9:.46,8);

    const tank={x:12,y:50,w:w*.56-18,h:h-70};
    const brain={x:w*.59,y:50,w:w*.22,h:h-105};
    this.drawTank(tank,now);
    this.drawBrain(brain,now);

    const signals=this.displaySignals;
    const gx=w*.83,gw=Math.max(70,w*.15);
    this.gauge('VISUAL',signals.visual_salience,gx,68,gw);
    this.gauge('AROUSAL',signals.arousal,gx,94,gw);
    this.gauge('PERSIST',signals.persistence,gx,120,gw);
    this.gauge('INHIBIT',signals.inhibition,gx,146,gw);
    this.gauge('LEFT',signals.motor_left,gx,172,gw);
    this.gauge('RIGHT',signals.motor_right,gx,198,gw);

    this.label(
      loaded?String(this.state?.dataset||'LOCAL DATASET').toUpperCase():'NO BIOLOGICAL ACTIVITY SHOWN UNTIL REAL DATA IS LOADED',
      w*.59,h-13,loaded?.70:.52,7
    );
  }
}
