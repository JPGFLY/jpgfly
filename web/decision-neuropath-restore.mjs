import {BrainActivityView} from './attribution-graph.mjs?v=firing-rates-smooth-2';

const anchor=document.querySelector('.neuropaths-head');
if(anchor){
  let panel=document.querySelector('[data-decision-neuropath]');
  if(!panel){
    panel=document.createElement('section');
    panel.className='brain-panel decision-neuropath-panel';
    panel.dataset.decisionNeuropath='true';
    panel.setAttribute('aria-label','Live JPGFLY neural and decision activity');
    panel.innerHTML=`
      <div class="brain-visual">
        <div class="bar"><span>LIVE DECISION NEUROPATH</span><span>SIGNAL / Hz / RECORDED DECISION</span></div>
        <canvas id="brain-canvas" width="900" height="300" aria-label="Live firing-rate dashboard from MaleCNS, ZebraCNS and derived JPGFLY decision telemetry"></canvas>
      </div>
      <aside class="brain-readout">
        <p class="kicker">ART BRAIN / LIVE SIGNALS</p>
        <h2>DECISION FIRING PATH</h2>
        <p class="brain-status" id="brain-status">Waiting for the next canvas observation.</p>
        <p>Recorded MaleCNS, ZebraCNS and JPGFLY decision signals are shown as a live firing path. The interface stays monochrome; only active neural/decision signals carry color.</p>
        <ul class="brain-clusters"><li>VISUAL SALIENCE</li><li>AROUSAL</li><li>ESCAPE</li><li>STEER L/R</li><li>FORWARD</li><li>COMPOSITION</li><li>BRUSH</li><li>ACTION</li></ul>
      </aside>`;
    anchor.parentNode.insertBefore(panel,anchor);
  }

  const canvas=panel.querySelector('#brain-canvas');
  const status=panel.querySelector('#brain-status');
  const view=new BrainActivityView(canvas,status);
  let sessionId='';
  let decisionCursor=0;
  let eventCursor=0;
  let fallbackTimer=null;
  let busy=false;
  let lastSharedAt=0;
  let resizeFrame=0;

  function consumeDelta(data){
    if(!data||typeof data!=='object')return;
    lastSharedAt=performance.now();
    if(data.reset||!sessionId||data.session_id!==sessionId){
      sessionId=data.session_id||'';
      decisionCursor=0;
      eventCursor=0;
    }
    for(const record of (data.actions||[]))view.pushDecision(record);
    for(const event of (data.events||[])){
      if(event?.type==='fly_comment'&&event.text){
        view.pushComment({text:event.text,provider:event.provider||data.language_state?.provider||''});
      }
    }
    view.setLanguageState(data.language_state||{});
    decisionCursor=Number(data.decision_count||decisionCursor);
    eventCursor=Number(data.event_count||eventCursor);
  }

  const TAP_KEY='__jpgflyDecisionDeltaTapV2';
  let tap=window[TAP_KEY];
  if(!tap){
    const nativeFetch=window.fetch.bind(window);
    tap={nativeFetch,listeners:new Set()};
    window[TAP_KEY]=tap;
    window.fetch=async(...args)=>{
      const response=await nativeFetch(...args);
      try{
        const input=args[0];
        const url=typeof input==='string'?input:String(input?.url||'');
        if(url.includes('/api/studio/delta')&&response.ok){
          const clone=response.clone();
          clone.json().then(data=>{
            for(const listener of tap.listeners){
              try{listener(data);}catch(error){console.warn('decision neuropath shared delta',error);}
            }
          }).catch(()=>{});
        }
      }catch{}
      return response;
    };
  }
  tap.listeners.add(consumeDelta);

  function scheduleFallback(delay){
    if(fallbackTimer!==null)clearTimeout(fallbackTimer);
    fallbackTimer=setTimeout(fallbackPoll,delay);
  }

  async function fallbackPoll(){
    if(busy){scheduleFallback(1800);return;}
    if(document.hidden){scheduleFallback(5000);return;}
    if(lastSharedAt&&performance.now()-lastSharedAt<3200){
      scheduleFallback(2500);
      return;
    }
    busy=true;
    try{
      const params=new URLSearchParams({
        after_decision:String(decisionCursor),
        after_event:String(eventCursor)
      });
      if(sessionId)params.set('session_id',sessionId);
      const controller=new AbortController();
      const timeout=setTimeout(()=>controller.abort(),6500);
      let response;
      try{
        response=await tap.nativeFetch(`/api/studio/delta?${params}`,{cache:'no-store',signal:controller.signal});
      }finally{
        clearTimeout(timeout);
      }
      if(response.status===404){scheduleFallback(3500);return;}
      if(!response.ok)throw new Error(`decision neuropath ${response.status}`);
      consumeDelta(await response.json());
      scheduleFallback(2500);
    }catch(error){
      console.warn('decision neuropath fallback poll',error);
      scheduleFallback(4500);
    }finally{
      busy=false;
    }
  }

  const requestResize=()=>{
    if(resizeFrame)return;
    resizeFrame=requestAnimationFrame(()=>{
      resizeFrame=0;
      view.resize();
    });
  };
  const ro=new ResizeObserver(requestResize);
  ro.observe(panel);
  document.addEventListener('visibilitychange',()=>{
    if(!document.hidden){
      requestResize();
      scheduleFallback(0);
    }
  },{passive:true});
  scheduleFallback(2500);
}
