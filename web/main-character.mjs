import {renderFlyPortrait} from './art-engine.mjs?v=fly-no-mouth-no-fins-20260917-8';

const canvases=[...document.querySelectorAll('[data-jpgfly-main-character]')];
const reduceMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
const visible=new Set();
const contexts=new WeakMap();
let lastPaint=0;
let loopRunning=false;

function applySize(canvas,widthCss,heightCss){
  const dpr=Math.min(window.devicePixelRatio||1,1.25);
  const width=Math.max(1,Math.round(widthCss*dpr));
  const height=Math.max(1,Math.round(heightCss*dpr));
  if(canvas.width!==width||canvas.height!==height){
    canvas.width=width;
    canvas.height=height;
    return true;
  }
  return false;
}

function ensureInitialSize(canvas){
  const box=canvas.getBoundingClientRect();
  applySize(canvas,box.width,box.height);
}

function paint(canvas,time){
  if(!canvas.width||!canvas.height)return;
  let ctx=contexts.get(canvas);
  if(!ctx){
    ctx=canvas.getContext('2d',{alpha:true});
    contexts.set(canvas,ctx);
  }
  renderFlyPortrait(ctx,{
    time,
    inkColor:canvas.dataset.inkColor||'#b85f43',
    brushDown:false,
    background:null
  });
}

function startLoop(){
  if(reduceMotion||loopRunning||document.hidden||!visible.size)return;
  loopRunning=true;
  requestAnimationFrame(tick);
}

function tick(time=0){
  if(document.hidden||!visible.size){
    loopRunning=false;
    return;
  }
  if(time-lastPaint>=50||!lastPaint){
    lastPaint=time;
    for(const canvas of visible)paint(canvas,time);
  }
  requestAnimationFrame(tick);
}

if(canvases.length){
  for(const canvas of canvases)ensureInitialSize(canvas);

  const resizeObserver=new ResizeObserver(entries=>{
    for(const entry of entries){
      const canvas=entry.target;
      const changed=applySize(canvas,entry.contentRect.width,entry.contentRect.height);
      if(changed&&(reduceMotion||visible.has(canvas)))paint(canvas,performance.now());
    }
  });
  for(const canvas of canvases)resizeObserver.observe(canvas);

  if('IntersectionObserver' in window){
    const observer=new IntersectionObserver(entries=>{
      for(const entry of entries){
        const canvas=entry.target;
        if(entry.isIntersecting){
          visible.add(canvas);
          paint(canvas,performance.now());
        }else{
          visible.delete(canvas);
        }
      }
      startLoop();
    },{rootMargin:'180px 0px',threshold:0});
    for(const canvas of canvases)observer.observe(canvas);
  }else{
    for(const canvas of canvases)visible.add(canvas);
  }

  if(reduceMotion){
    for(const canvas of canvases)paint(canvas,0);
  }else{
    startLoop();
  }

  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){
      loopRunning=false;
      return;
    }
    for(const canvas of visible)paint(canvas,performance.now());
    startLoop();
  },{passive:true});
}
