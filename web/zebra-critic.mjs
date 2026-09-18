const MIN_CRITIC_DWELL_MS=7600;
const RECENT_QUOTE_LIMIT=8;
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)||0));

function hashIndex(value,length){
  let h=2166136261;
  for(const ch of String(value||'')){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)}
  return Math.abs(h)%Math.max(1,length);
}

function clean(value,fallback='move'){
  return String(value||fallback).replaceAll('_',' ').replace(/\s+/g,' ').trim().toLowerCase();
}

function pct(value){return Math.round(clamp(value)*100)}
function num(value,fallback=0){const n=Number(value);return Number.isFinite(n)?n:fallback}

function hasRealData(state){
  return !!(state?.connected&&(state.biological_data_loaded||state.activity_loaded||state.connectome_loaded));
}

function scoreState(state){
  const s=state?.signals||{};
  const novelty=clamp(s.novelty_seek);
  const attention=clamp(s.attention_lock);
  const persistence=clamp(s.persistence);
  const repetition=clamp(s.repetition_drive);
  const instability=clamp(s.state_instability);
  const escape=clamp(s.escape_drive);
  const visual=clamp(s.visual_salience);
  const inhibition=clamp(s.inhibition);
  return clamp(
    .47+novelty*.18+attention*.14+persistence*.09+visual*.08
    -repetition*.17-instability*.16-escape*.10-inhibition*.04
  );
}

function chooseFresh(lines,key,recent=[]){
  if(!lines.length)return '';
  const start=hashIndex(key,lines.length);
  for(let offset=0;offset<lines.length;offset++){
    const candidate=lines[(start+offset)%lines.length];
    if(!recent.includes(candidate))return candidate;
  }
  return lines[start];
}

function makeCritique(state,context={},recent=[],toneOverride=''){
  const s=state?.signals||{};
  const action=context.action||{};
  const obs=context.observation||{};
  const sequence=num(context.sequence);
  const artist=String(context.agentName||'JPGFLY').replace(/\s+/g,' ').trim().slice(0,40)||'JPGFLY';
  const profile=String(context.agentProfile||'jpgfly').trim().toLowerCase();
  const completion=clamp(s.completion_pressure);
  const repetition=clamp(s.repetition_drive);
  const novelty=clamp(s.novelty_seek);
  const attention=clamp(s.attention_lock);
  const persistence=clamp(s.persistence);
  const instability=clamp(s.state_instability);
  const escape=clamp(s.escape_drive);
  const arousal=clamp(s.arousal);
  const tempo=clamp(s.tempo);
  const visual=clamp(s.visual_salience);
  const score=scoreState(state);

  const movement=clean(action.movementStyle||action.movement_style||'move');
  const motif=action.motifHint&&action.motifHint!=='NONE'?clean(action.motifHint):'shape';
  const composition=clean(action.compositionMode||action.composition_mode||'composition');
  const phase=clean(action.phase||action.compositionPass||action.composition_pass||'current phase');
  const brush=clean(action.brushTool||action.brush_tool||'brush');
  const pressure=clamp(action.pressure);
  const criticPressure=Math.max(-.42,Math.min(.42,num(action.zebracnsCriticPressure)));
  const intersections=num(obs.intersections);
  const occupancy=clamp(obs.canvasOccupancy??obs.canvas_occupancy);
  const coverage=clamp(obs.coverage??obs.inkCoverage??obs.ink_coverage??occupancy);
  const density=occupancy>.67?'dense':occupancy>.38?'mid-density':'open';
  const collision=intersections>=18?'collision-heavy':intersections>=8?'intersecting':'cleanly separated';

  let tone='MIXED';
  if(completion>.82)tone='MIXED';
  else if(repetition>.84&&(novelty<.48||attention<.58))tone='ROAST';
  else if(instability>.84&&escape>.67)tone='ROAST';
  else if(score>.64&&attention>.53)tone='GOOD';
  else if(novelty>.67||visual>.72)tone='CURIOUS';
  else if(score>.54)tone='GOOD';

  if(toneOverride)tone=toneOverride;

  const shared=[
    `The canvas is ${density}, the path is ${collision}, and that matters more than whether I personally like it.`,
    `You are using ${movement} with the ${brush}; I am watching what that does to the ${composition}, not grading vibes.`,
    `${pct(occupancy)}% occupancy and ${intersections} intersections: the structure is giving me more to say than "good" or "bad".`,
    `The ${phase} is carrying ${motif} through a ${density} field. I want to see whether the next move clarifies that relationship.`,
    profile==='sprayfly'
      ?`${artist} is supposed to think in impact and overwrite; I am watching whether the damage actually reorganizes the wall.`
      :profile==='dreamfly'
        ?`${artist} is supposed to distort space; I am watching whether the weirdness changes the room rather than merely decorating it.`
        :`${artist} has the widest vocabulary, so the standard is coherence: variety only matters when the room still has an argument.`
  ];

  const banks={
    GOOD:[
      `That ${movement} actually changed the balance. Keep the ${motif}; it is doing structural work now.`,
      `The ${composition} is holding together under ${pct(attention)}% attention lock. Do not confuse restraint with inactivity.`,
      `The ${brush} choice makes sense here. The mark feels earned instead of merely available.`,
      `You gave the ${motif} room to breathe. That is better than filling every quiet area just because you can.`,
      `The canvas is ${density} without feeling clogged. That is a useful tension; protect it.`,
      `${intersections} intersections and the image still reads. Good. The crossings are becoming structure instead of noise.`,
      `The ${movement} has a reason now. It is redirecting the eye instead of just proving the agent is active.`,
      `Novelty is at ${pct(novelty)}%, but this does not feel random. That is the interesting part.`,
      `I like the decision to stay with the ${composition}. It is becoming a position, not a default.`,
      `Pressure at ${pct(pressure)}% suits this ${brush} move. More force would flatten the distinction you just made.`
    ],
    CURIOUS:[
      `Why repeat the ${motif} here? If the answer is rhythm, make the next repetition change the rhythm.`,
      `The ${movement} pulled my eye away from the center. Was that the intention, or did the system discover it accidentally?`,
      `This ${phase} is more interesting than the last one because the canvas is only ${pct(occupancy)}% occupied. What happens if you leave the gap alone?`,
      `The ${composition} is starting to imply a hierarchy. I want to know which shape ${artist} thinks is in charge.`,
      `Visual salience is ${pct(visual)}%. Something is demanding attention; the next mark should answer it, not merely join it.`,
      `The ${brush} against this ${motif} is an odd pairing. Keep it long enough to prove whether the mismatch is useful.`,
      `There are ${intersections} intersections now. Which one is the actual event and which ones are just traffic?`,
      `The piece is ${density}, but not settled. I would rather see one decisive contradiction than five polite additions.`,
      `Attention lock is ${pct(attention)}%. The fish is convinced something matters here; I am not yet sure what.`,
      `This is the first moment I would ask ${artist} a question instead of giving it a grade: what are you protecting in this ${composition}?`
    ],
    MIXED:[
      `The ${motif} is readable, but the ${movement} is not yet telling me why it belongs in this ${phase}.`,
      `I do not hate this. I also do not believe it yet. The next decision needs to make the ${composition} more specific.`,
      `${pct(repetition)}% repetition drive is not automatically a problem. It becomes one if the repeated mark stops changing the image.`,
      `The ${brush} is doing competent work. Competence is not the same thing as a point of view.`,
      `The canvas is ${density}; I would test subtraction before adding another family of marks.`,
      `The ${movement} is fine. The question is whether it changes the relationship between the ${motif} and the rest of the room.`,
      `I can see the ${phase} developing, but I cannot yet tell which choice is irreversible. Give me one.`,
      `There are ${intersections} intersections. A few feel intentional; a few feel like ${artist} arrived late to its own composition.`,
      `Persistence is ${pct(persistence)}%. Stay with the problem, but do not mistake staying for solving.`,
      `This is neither failure nor breakthrough. It is a fork. The next ${movement} decides which.`
    ],
    ROAST:[
      `Repetition is at ${pct(repetition)}%. If the ${motif} comes back again, it needs a new job, not a new address.`,
      `The ${movement} is repeating itself so hard it has become background noise. Break the pattern or own it completely.`,
      `The ${composition} is not collapsing, but it is definitely sending me a resignation letter.`,
      `Instability is ${pct(instability)}% and escape drive is ${pct(escape)}%. The system is fleeing the problem instead of resolving it.`,
      `I have seen enough of that ${brush} gesture. Change scale, direction, pressure — anything that makes it a decision again.`,
      `${artist} is busy. The image is not. Those are different things.`,
      `At ${intersections} intersections, one more collision will not automatically become complexity.`,
      `This ${phase} needs editing, not another alibi in paint.`
    ],
    FINISH:[
      `Completion pressure is ${pct(completion)}%. The difficult move now may be leaving the room alone.`,
      `The work is asking for a stop more loudly than it is asking for another ${movement}.`,
      `You have enough evidence on the canvas. Finishing would be a decision; continuing may just be anxiety with a brush.`,
      `Before adding anything else, point to the exact problem the next mark solves. If there is none, stop.`,
      `The ${composition} can survive being unfinished-looking. It may not survive being over-explained.`,
      `I would rather archive this tension than watch ${artist} sand it smooth.`
    ]
  };

  let lines=completion>.82?banks.FINISH:[...(banks[tone]||banks.MIXED),...shared];

  if(sequence>0&&sequence%6===0){
    lines=[
      `System note: this is strongest when ZebraCNS disagrees with ${artist} for a concrete reason. Right now that reason is ${repetition>.6?'repetition':novelty>.6?'novelty':attention>.6?'attention':'composition'}.`,
      `Meta-critique: the interesting part is not that an agent made a mark; it is whether the next decision changes the logic of the room.`,
      `I am not here to roast on schedule. I am here to notice when the ${movement}, ${motif}, and ${composition} stop agreeing with each other.`,
      ...lines
    ];
  }

  const key=[
    state?.frame||0,sequence,tone,state?.action||'NONE',profile,artist,movement,motif,composition,brush,
    Math.round(repetition*20),Math.round(novelty*20),Math.round(instability*20),
    Math.round(completion*20),intersections,Math.round(occupancy*20)
  ].join(':');

  const quote=chooseFresh(lines,key,recent);
  const reasons=[];
  if(novelty>.58)reasons.push(`novelty ${pct(novelty)}%`);
  if(repetition>.58)reasons.push(`repetition ${pct(repetition)}%`);
  if(attention>.58)reasons.push(`attention ${pct(attention)}%`);
  if(instability>.58)reasons.push(`instability ${pct(instability)}%`);
  if(completion>.62)reasons.push(`finish pressure ${pct(completion)}%`);
  if(arousal>.62)reasons.push(`arousal ${pct(arousal)}%`);
  if(intersections>0)reasons.push(`${intersections} intersections`);
  if(coverage>0)reasons.push(`coverage ${pct(coverage)}%`);
  if(!reasons.length)reasons.push(`${density} canvas`,`${clean(state?.action||'none')} neural action`);

  return {
    tone,
    quote,
    thought:`Zebra reads: ${reasons.slice(0,4).join(' · ')}.`,
    decoder:`decoder ${String(state?.action||'NONE').toLowerCase()} · score ${score.toFixed(2)} · pressure ${criticPressure>=0?'+':''}${criticPressure.toFixed(2)}`,
    talkMs:Math.max(1700,Math.min(4200,Math.round(quote.length*24+700-tempo*250)))
  };
}

export class ZebraCritic{
  constructor(root){
    this.root=root;
    this.quote=root?.querySelector('[data-zebra-quote]')||null;
    this.thought=root?.querySelector('[data-zebra-thought]')||null;
    this.mood=root?.querySelector('[data-zebra-mood]')||null;
    this.decoder=root?.querySelector('[data-zebra-decoder]')||null;
    this.character=root?.querySelector('[data-zebra-character]')||null;
    this.mouth=root?.querySelector('.zebra-cli-mouth')||null;
    this.lastKey='';
    this.lastTone='';
    this.lastSpokenAt=0;
    this.recentQuotes=[];
    this.timer=null;
  }

  push(state,context={}){
    if(!this.root)return;
    if(!hasRealData(state)){
      const artist=String(context.agentName||'JPGFLY').replace(/\s+/g,' ').trim().slice(0,40)||'JPGFLY';
      if(this.quote)this.quote.textContent=`I need the real ZebraCNS feed before I start judging ${artist}.`;
      if(this.thought)this.thought.textContent='Critic dormant: no biological activity data is currently available.';
      if(this.mood)this.mood.textContent='DORMANT';
      if(this.decoder)this.decoder.textContent='waiting for ZebraCNS';
      this.root.dataset.tone='dormant';
      this.stopTalking();
      return;
    }

    let critique=makeCritique(state,context,this.recentQuotes);
    if(critique.tone==='ROAST'&&this.lastTone==='ROAST'){
      critique=makeCritique(state,context,this.recentQuotes,'MIXED');
    }

    const sequence=Number(context.sequence||0);
    const frameBucket=Math.floor(Number(state?.frame||0)/8);
    const key=`${sequence}:${frameBucket}:${critique.tone}:${critique.quote}`;
    const now=performance.now();
    const shouldSpeak=key!==this.lastKey&&(this.lastSpokenAt===0||now-this.lastSpokenAt>=MIN_CRITIC_DWELL_MS);

    this.root.dataset.tone=critique.tone.toLowerCase();
    this.root.dataset.sequence=String(sequence);
    if(this.mood)this.mood.textContent=critique.tone;
    if(this.decoder)this.decoder.textContent=critique.decoder;

    if(shouldSpeak){
      this.lastKey=key;
      this.lastTone=critique.tone;
      this.lastSpokenAt=now;
      this.recentQuotes.push(critique.quote);
      if(this.recentQuotes.length>RECENT_QUOTE_LIMIT)this.recentQuotes.splice(0,this.recentQuotes.length-RECENT_QUOTE_LIMIT);
      if(this.quote)this.quote.textContent=critique.quote;
      if(this.thought)this.thought.textContent=critique.thought;
      this.talk(critique.talkMs);
    }
  }

  talk(duration=1800){
    if(!this.mouth)return;
    this.mouth.classList.remove('is-speaking');
    void this.mouth.getBoundingClientRect();
    const ms=Math.max(1200,Number(duration)||1800);
    this.mouth.classList.add('is-speaking');
    clearTimeout(this.timer);
    this.timer=setTimeout(()=>this.stopTalking(),ms);
  }

  stopTalking(){
    clearTimeout(this.timer);
    this.timer=null;
    this.mouth?.classList.remove('is-speaking');
  }
}
