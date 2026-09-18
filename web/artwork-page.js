import{formatDate,TIME_STANDARD}from'./backroom.js?v=identity-utc-6';

const root=document.querySelector('#piece-root');
const sessionId=decodeURIComponent(location.pathname.split('/').filter(Boolean).at(-1)||'');

const fmt=ms=>{
  const seconds=Math.floor(Math.max(0,Number(ms)||0)/1000);
  return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};

function node(tag,className,text){
  const e=document.createElement(tag);
  if(className)e.className=className;
  if(text!==undefined)e.textContent=text;
  return e;
}

function fact(label,value){
  const row=node('div','fact');
  row.append(node('small','',label),node('code','',value??'-'));
  return row;
}

function addNarrative(copy,label,text){
  if(!text)return;
  copy.append(node('p','backroom-kicker',label),node('p','backroom-lead',text));
}

function publicHistory(data){
  const section=node('section','piece-section');
  section.append(
    node('p','backroom-kicker','PUBLIC MEMORY'),
    node('h2','backroom-heading','WHAT THE FLY SAID / OVER TIME')
  );

  const list=node('div','history-list');
  const comments=Array.isArray(data.public_commentary)?data.public_commentary:[];

  if(comments.length){
    comments.forEach((entry,index)=>{
      const item=node('article','history-entry');
      item.append(
        node('small','',`COMMENT ${String(index+1).padStart(2,'0')} / DECISION ${entry.sequence??'-'} / ${fmt(entry.timestamp||0)}`),
        node('p','',entry.text||'')
      );
      list.append(item);
    });
  }else{
    for(const [index,text] of (data.thought_fragments||[]).entries()){
      const item=node('article','history-entry');
      item.append(
        node('small','',`RECORDED NOTE ${String(index+1).padStart(2,'0')}`),
        node('p','',text)
      );
      list.append(item);
    }
  }

  if(!list.children.length){
    const item=node('article','history-entry');
    item.append(node('p','','No public commentary was recorded for this room.'));
    list.append(item);
  }

  section.append(list);
  return section;
}

function zebraCriticCli(data){
  const section=node('section','piece-section');
  section.append(
    node('p','backroom-kicker','ROOM CRITIC'),
    node('h2','backroom-heading','ZEBRA CRITIC / FINAL REVIEW')
  );

  const wrap=node('div','room-zebra-critic');
  const fish=node('pre','room-zebra-fish');
  fish.textContent=[
    'ZEBRACNS://DANIO_RERIO',
    '',
    '           /\\',
    '      ____/  \\___',
    '   __/ o  /// /// `-.',
    '  <   /// ///      >',
    '   \\__///_///__.-\'',
    '       \\_/',
    '',
    '[ ARCHIVED CRITIC ]'
  ].join('\n');

  const copy=node('div','room-zebra-copy');
  const critique=String(data.zebra_critique||'').trim();
  const review=node('blockquote','room-zebra-review',
    critique||'No authentic Zebra critic trajectory was archived for this room. This room predates the saved final-critique record.'
  );
  const count=Number(data.zebra_critic_observation_count||0);
  const note=node('small','room-zebra-truth',
    count
      ?`Final review distilled from ${count} saved ZebraCNS/painting observations across this room. Character voice is engineered; the biological recording itself is not speaking.`
      :'No retrospective critique is fabricated when the original Zebra trajectory is unavailable.'
  );
  copy.append(review,note);
  wrap.append(fish,copy);
  section.append(wrap);
  return section;
}

function lineageSection(data){
  const section=node('section','piece-section');
  section.append(node('p','backroom-kicker','ROOM-BORN ARTIST'),node('h2','backroom-heading',`${data.agent_name||'JPGFLY'} / ${(data.agent_profile||'jpgfly').toUpperCase()}`));
  const copy=node('div','history-list');
  const identity=node('article','history-entry');identity.append(node('small','',data.spawned_from?`SPAWNED FROM ${data.spawned_from}`:'ORIGIN LINE'),node('p','',data.agent_lore||'The original JPGFLY room line.'));copy.append(identity);
  if(data.agent_echo_rule){const rule=node('article','history-entry plan');rule.append(node('small','','CROSS-ROOM RULE'),node('p','',data.agent_echo_rule));copy.append(rule);}
  for(const echo of (data.room_echoes||[]).slice(0,4)){
    const item=node('article','history-entry plan');const label=node('small','',`ECHO / ${echo.room_code||'ROOM'} / ${echo.agent_name||'JPGFLY'}`);const text=node('p','',echo.room_title||'Earlier room');
    if(echo.session_id){const link=node('a','backroom-action','OPEN ECHO');link.href=`/artworks/${encodeURIComponent(echo.session_id)}`;item.append(label,text,link);}else item.append(label,text);copy.append(item);
  }
  section.append(copy);return section;
}

function structureSection(data){
  const metrics=data.structural_metrics||{};
  const section=node('section','piece-section');
  section.append(
    node('p','backroom-kicker','COMPACT ROOM RECORD'),
    node('h2','backroom-heading','WHAT STAYS')
  );

  const grid=node('div','piece-facts');
  const families=Array.isArray(metrics.markFamilies)?metrics.markFamilies.join(', '):'-';
  const brushes=Array.isArray(metrics.brushTools)?metrics.brushTools.join(', '):'-';
  const techniques=Array.isArray(metrics.techniques)?metrics.techniques.join(', '):'-';

  grid.append(
    fact('ARCHIVE MODE','IMAGE + LLM TEXT ONLY'),
    fact('MARK FAMILIES',families),
    fact('BRUSHES',brushes),
    fact('TECHNIQUES',techniques),
    fact('INTERSECTIONS',metrics.intersections),
    fact('MOTIF DEVELOPMENTS',metrics.motifDevelopments),
    fact('SELECTIVE ERASURES',metrics.erasureActions)
  );

  section.append(grid);
  return section;
}

function build(data){
  root.textContent='';
  document.title=`JPGFLY / ${data.room_code||'ROOM'}`;

  const head=node('section','piece-head');
  const visual=node('div','piece-visual');
  const image=node('img');
  image.src=`/api/artworks/${encodeURIComponent(data.session_id)}/artwork.svg`;
  image.alt=data.room_title||'JPGFLY room drawing';
  visual.append(image);

  const copy=node('div','piece-copy');
  copy.append(
    node('p','backroom-kicker',data.room_code||'ARCHIVED ROOM'),
    node('h1','',data.room_title||'UNNAMED ROOM'),
    node('p','piece-concept',data.room_description||data.concept||'A completed fly drawing.')
  );
  addNarrative(copy,'MEMORY THREAD',data.memory_thread);
  addNarrative(copy,'ANOMALY REPORT',data.anomaly_report);
  addNarrative(copy,'FLY STATEMENT',data.fly_statement);
  copy.append(node('p','backroom-kicker',`ARCHIVED ${formatDate(data.completed_at)}`));

  head.append(visual,copy);
  root.append(head);
  root.append(lineageSection(data));

  const factsSection=node('section','piece-section');
  factsSection.append(
    node('p','backroom-kicker','ROOM RECORD'),
    node('h2','backroom-heading','IMAGE + WRITING')
  );

  const facts=node('div','piece-facts');
  const visualContext=data.visual_context||{};
  const memoryAxes=Array.isArray(visualContext.context_pressures)?visualContext.context_pressures.join(', '):'-';
  const compressed=Number(data.storage?.artworkCompressedBytes||0);
  const raw=Number(data.storage?.artworkRawBytes||0);
  const imageStorage=compressed
    ?`${(compressed/1024).toFixed(1)} KB gzip${raw?` / ${(raw/1024).toFixed(1)} KB raw`:''}`
    :'compressed SVG';

  facts.append(
    fact('ROOM',data.room_code),
    fact('COMPLETED',formatDate(data.completed_at)),
    fact('TIME STANDARD',TIME_STANDARD),
    fact('SESSION',data.session_id),
    fact('FINGERPRINT',data.hashes?.fingerprint),
    fact('DRAWING RUNTIME',fmt(data.duration)),
    fact('BRAIN DECISIONS',data.decision_count),
    fact('ROOM TENSION',visualContext.room_tension||'-'),
    fact('SPATIAL PROGRAM',visualContext.spatial_program||'-'),
    fact('STROKE DIALECT',visualContext.stroke_dialect||'-'),
    fact('DURATION PROFILE',visualContext.duration_profile||'-'),
    fact('TEMPO',visualContext.tempo_mode||'-'),
    fact('CONTENT REGISTER',visualContext.content_register||'-'),
    fact('ARCHETYPE',visualContext.archetype||'-'),
    fact('MEMORY CONTEXT',memoryAxes),
    fact('MEMORY DEPTH',`${visualContext.rooms_seen||0} rooms / ${visualContext.readings_seen||0} readings`),
    fact('IMAGE STORAGE',imageStorage),
    fact('REPLAY','NOT STORED'),
    fact('VIDEO','NOT STORED'),
    fact('COMPLETION',data.completion_reason),
    fact('BRAIN',`${data.brain_mode} / ${data.brain_version}`),
    fact('TEXT MODEL',data.text_provider||'PROCEDURAL')
  );
  factsSection.append(facts);
  root.append(factsSection);

  root.append(publicHistory(data));
  root.append(zebraCriticCli(data));
  root.append(structureSection(data));

  const thoughtSection=node('section','piece-section');
  thoughtSection.append(
    node('p','backroom-kicker','SELECTED ACTION NOTES'),
    node('h2','backroom-heading','ROOM NOTES')
  );
  const thoughts=node('div','thoughts');
  for(const text of data.thought_fragments||[])thoughts.append(node('p','thought',text));
  if(!thoughts.children.length)thoughts.append(node('p','thought','No selected action notes were recorded.'));
  thoughtSection.append(thoughts);
  root.append(thoughtSection);
}

fetch(`/api/artworks/${encodeURIComponent(sessionId)}`,{cache:'no-store'})
  .then(r=>{if(!r.ok)throw new Error();return r.json()})
  .then(build)
  .catch(()=>{
    root.textContent='';
    root.append(
      node('p','backroom-kicker','ROOM NOT FOUND'),
      node('h1','backroom-heading','THE FLY LEFT NO RECORD HERE.')
    );
  });
