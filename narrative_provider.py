"""GPU-backed public narrative helpers for JPGFLY."""
from __future__ import annotations

import json
import os
import random
import re
import urllib.request
from typing import Any


def narrative_mode() -> str:
    value=os.environ.get("JPGFLY_TEXT_PROVIDER","procedural").strip().lower()
    return value if value in {"procedural","ollama","flm","hybrid"} else "procedural"


def clean_public_text(value:Any,limit:int)->str:
    text=re.sub(r"\s+"," ",str(value or "")).strip()
    text=re.sub(r"^(?:```[A-Za-z0-9_-]*\s*|#{1,6}\s+|>\s+)","",text).strip()
    if len(text)>limit:
        cut=text[:limit]
        if limit<len(text) and not text[limit].isspace():
            boundary=cut.rfind(" ")
            if boundary>=max(0,int(limit*.70)):
                cut=cut[:boundary]
        text=cut
    text=text.rstrip(" \t\r\n`#*_>-–—/:;,")
    parts=text.rsplit(" ",1)
    if len(parts)==2 and len(parts[1])==1 and parts[1].isalpha() and parts[1]!="I":
        text=parts[0].rstrip()
    return text

def _clean(value:Any,limit:int)->str:
    return clean_public_text(value,limit)


def _active_artist(context:dict[str,Any])->tuple[str,str]:
    agent=context.get("agent") if isinstance(context.get("agent"),dict) else {}
    name=str(context.get("agent_name") or agent.get("name") or "JPGFLY").strip()[:48] or "JPGFLY"
    profile=str(context.get("agent_profile") or agent.get("profile") or "jpgfly").strip().casefold()[:24] or "jpgfly"
    return name,profile


def _ollama(prompt:str,seed:int,max_tokens:int,temperature:float)->str:
    url=os.environ.get("JPGFLY_OLLAMA_URL","http://127.0.0.1:11434").rstrip("/")
    model=os.environ.get("JPGFLY_OLLAMA_MODEL","qwen3:8b").strip() or "qwen3:8b"
    payload={
        "model":model,
        "prompt":prompt,
        "stream":False,
        "format":"json",
        "options":{
            "temperature":temperature,
            "top_p":float(os.environ.get("JPGFLY_OLLAMA_TOP_P","0.92")),
            "top_k":int(os.environ.get("JPGFLY_OLLAMA_TOP_K","50")),
            "min_p":float(os.environ.get("JPGFLY_OLLAMA_MIN_P","0.05")),
            "repeat_penalty":float(os.environ.get("JPGFLY_OLLAMA_REPEAT_PENALTY","1.18")),
            "repeat_last_n":int(os.environ.get("JPGFLY_OLLAMA_REPEAT_LAST_N","512")),
            "num_predict":max_tokens,
            "num_ctx":int(os.environ.get("JPGFLY_OLLAMA_CONTEXT","8192")),
            "seed":int(seed)&0x7fffffff,
        },
    }
    headers={"content-type":"application/json"}
    auth_token=os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
    if auth_token:
        headers["authorization"]="Bearer "+auth_token
    req=urllib.request.Request(
        url+"/api/generate",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )
    timeout=max(5,min(120,int(os.environ.get("JPGFLY_OLLAMA_TIMEOUT","45"))))
    with urllib.request.urlopen(req,timeout=timeout) as response:
        data=json.load(response)
    text=str(data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama returned no text")
    return text


def _json(text:str)->dict[str,Any]:
    text=(text or "").strip()
    candidates=[text]
    found=re.search(r"\{[\s\S]*\}",text)
    if found:
        candidates.append(found.group(0))
    for candidate in candidates:
        try:
            data=json.loads(candidate)
            if isinstance(data,dict):
                return data
        except Exception:
            pass
    raise RuntimeError("Narrative reply was not valid JSON")


VOICE_ANGLES=(
    "FORM_AND_PERCEPTION",
    "ARCHITECTURE_AND_SPACE",
    "MATERIAL_AND_SURFACE",
    "MEMORY_AND_RETURN",
    "MORTALITY_AND_RESIDUE",
    "DOMESTIC_LIFE",
    "WEATHER_AND_NATURE",
    "RITUAL_AND_REPETITION",
    "POETRY_AND_METAPHOR",
    "LABOR_AND_MAINTENANCE",
    "BODY_AND_TOUCH",
    "ABSURDITY",
    "VALUE_AND_BELIEF",
    "MACHINE_SYSTEMS",
)

CULTURAL_CONSTELLATIONS=(
    "automatic drawing, Surrealism, and the feeling of a hand moving before language catches up",
    "Louise Bourgeois: webs, care, threat, architecture and bodily memory",
    "Cy Twombly: scratches, handwriting, repetition and marks that almost become language",
    "Jean-Michel Basquiat: nervous symbols, street energy, crowns, damage and compressed language",
    "Joan Miró: signs hovering between creature, star, alphabet and private symbol",
    "Leonora Carrington: animal logic, dream ritual, metamorphosis and private myth",
    "Dubuffet and art brut: rude lines, anti-polish, graffiti, dirt and stubborn life",
    "Dada: collision, sabotage, found meaning and refusing tasteful order",
    "poetry built from fragments: image first, explanation later",
    "insects, rooms, street walls, bruises, trash, flowers, rot and fluorescent light",
    "architecture as behavior: corridors, thresholds, walls, pressure and escape",
    "weather systems, erosion, migration, nests, residue and accidental maps",
    "domestic objects becoming witnesses: chairs, windows, lamps, beds and empty rooms",
    "maintenance and labor: repair, repetition, wear, cleaning, breaking and rebuilding",
)

REGISTER_ANGLES={
    "FORMAL":("FORM_AND_PERCEPTION","MATERIAL_AND_SURFACE","POETRY_AND_METAPHOR"),
    "DOMESTIC":("DOMESTIC_LIFE","ARCHITECTURE_AND_SPACE","MEMORY_AND_RETURN"),
    "NATURAL":("WEATHER_AND_NATURE","MATERIAL_AND_SURFACE","RITUAL_AND_REPETITION"),
    "ARCHITECTURAL":("ARCHITECTURE_AND_SPACE","LABOR_AND_MAINTENANCE","FORM_AND_PERCEPTION"),
    "COSMIC":("RITUAL_AND_REPETITION","MEMORY_AND_RETURN","FORM_AND_PERCEPTION"),
    "MORTAL":("MORTALITY_AND_RESIDUE","MEMORY_AND_RETURN","MATERIAL_AND_SURFACE"),
    "ABSURD":("ABSURDITY","DOMESTIC_LIFE","FORM_AND_PERCEPTION"),
    "BODILY":("BODY_AND_TOUCH","MATERIAL_AND_SURFACE","MEMORY_AND_RETURN"),
}


def _context_recent_text(context:dict[str,Any])->str:
    bits=[]
    for room in (context.get("earlier_rooms") or [])[-4:]:
        if not isinstance(room,dict):
            continue
        for key in ("room_title","room_description","memory_thread","fly_statement"):
            value=room.get(key)
            if value:bits.append(str(value))
    for note in (context.get("recent_public_notes") or [])[-8:]:
        value=note.get("text") if isinstance(note,dict) else note
        if value:bits.append(str(value))
    return " ".join(bits).casefold()


def _choose_voice_angle(context:dict[str,Any],seed:int,offset:int=0)->str:
    visual=context.get("visual_context") or {}
    register=str(visual.get("content_register") or "FORMAL")
    rng=random.Random(((int(seed)+offset)&0xffffffff)^0x3C6EF372)
    pool=list(REGISTER_ANGLES.get(register,REGISTER_ANGLES["FORMAL"]))
    recent=_context_recent_text(context)

    rare=[]
    if "crypto" not in recent and "bitcoin" not in recent:
        rare.append("MACHINE_SYSTEMS")
    if not any(word in recent for word in ("money","scarcity","market","crypto","bitcoin","memecoin")):
        rare.append("VALUE_AND_BELIEF")
    if register=="BODILY" and not any(word in recent for word in ("sex","sexual","erotic","desire","intimacy")):
        # BODY_AND_TOUCH is deliberately broader than eroticism; an erotic reading
        # may emerge only inside a body-led room, never as the default rotation.
        pool.append("BODY_AND_TOUCH")
    if register=="ABSURD" and not any(word in recent for word in ("joke","funny","satire","absurd","deadpan")):
        pool.append("ABSURDITY")
    if rare and rng.random()<.12:
        pool.append(rng.choice(rare))
    return rng.choice(pool)


def _choose_constellation(context:dict[str,Any],seed:int)->str:
    recent=_context_recent_text(context)
    rng=random.Random((int(seed)&0xffffffff)^0xA54FF53A)
    choices=list(CULTURAL_CONSTELLATIONS)
    # Avoid immediately recycling the same named association.
    filtered=[item for item in choices if not any(token in recent for token in re.findall(r"[a-zA-Z]{6,}",item.casefold())[:3])]
    return rng.choice(filtered or choices)


def _words(text:str)->set[str]:
    return {token for token in re.findall(r"[a-zA-ZÀ-ÿ0-9']+",(text or "").lower()) if len(token)>2}

def _similarity(a:str,b:str)->float:
    aa=_words(a);bb=_words(b)
    if not aa or not bb:return 0.0
    return len(aa&bb)/max(1,len(aa|bb))

def _comment_history(context:dict[str,Any])->list[str]:
    history=[]
    for entry in context.get("recent_public_notes") or []:
        text=entry.get("text") if isinstance(entry,dict) else entry
        if text:history.append(str(text))
    for room in context.get("earlier_rooms") or []:
        for entry in (room.get("public_commentary") or [])[-4:]:
            text=entry.get("text") if isinstance(entry,dict) else entry
            if text:history.append(str(text))
        for text in (room.get("thought_fragments") or [])[-3:]:
            if text:history.append(str(text))
    return history[-32:]

def _too_similar(comment:str,history:list[str])->bool:
    normalized=_clean(comment,1000).lower()
    if not normalized:return True
    for old in history:
        oldn=_clean(old,1000).lower()
        if not oldn:continue
        if normalized==oldn:return True
        if len(normalized)>36 and (normalized in oldn or oldn in normalized):return True
        if _similarity(normalized,oldn)>=.42:return True
    return False


def generate_live_comment(context:dict[str,Any],seed:int)->str|None:
    if narrative_mode() not in {"ollama","hybrid"}:
        return None

    history=_comment_history(context)
    angle=_choose_voice_angle(context,seed)
    theme=context.get("writing_theme") if isinstance(context.get("writing_theme"),dict) else {}
    theme_instruction=str(theme.get("instruction") or "")
    constellation=_choose_constellation(context,seed)
    avoid=history[-12:]
    earlier=[room for room in (context.get("earlier_rooms") or []) if isinstance(room,dict)]
    artist_name,artist_profile=_active_artist(context)
    painting_relation="none"
    if earlier and int(seed)%5==0:
        target=earlier[int(seed)%len(earlier)]
        title=_clean(target.get("room_title") or target.get("room_code"),120)
        if title:
            painting_relation=f"ACTIVE: mention {title} by name and let the current painting react to it like another artwork with a relationship to this one."

    prompt=f"""You are the public voice of {artist_name}, the active room-born JPGFLY artist ({artist_profile}), while she is drawing.

You are a serious contemporary painter speaking publicly from inside the Backrooms: visually alert, literate, composed, and sensual when appropriate.

TODAY'S ANGLE: {angle}
TODAY'S REQUIRED SUBJECT: {theme_instruction or "none"}
TODAY'S CULTURAL CONSTELLATION: {constellation}
PAINTING-TO-PAINTING MODE: {painting_relation}

The drawing record is factual grounding, but do not narrate telemetry. Use it as a trigger for painterly thought, cultural association, memory, poetry and ordinary life.
TODAY'S REQUIRED SUBJECT outranks TODAY'S ANGLE. If a required subject is present, make it unmistakable rather than hinting at it once.
{artist_name}'s artist persona has feelings and an adult sexual life. Most notes should reveal some affective reaction to painting: desire, lust, horniness, attraction, tenderness, jealousy, obsession, shame, pride, anger, loneliness, affection, relief, or love. Sex/eroticism may recur when connected to the marks; it is not forbidden or treated as a one-off gimmick. Keep physical detail non-graphic. Crypto, money/markets and jokes remain contextual rather than mandatory.
Technical/formal vocabulary should be rare. Do not keep saying composition, structure, motif, density, region, strategy, process, gesture, canvas, contrast, or "the drawing is becoming". Prefer what the marks evoke over how they were computed.
At most ONE sentence may directly describe the mechanics of the current picture. The rest should be thought, association, image, attitude, or poetry.

You may name artists, writers, movements or cultural references as ASSOCIATIONS, not as fake autobiography. Never claim "I read", "I met", "I remember seeing", or other life experiences you do not have.
Do not quote poems, songs, books, or living writers.
You may write first-person inner feeling as part of {artist_name}'s fictional artist persona. Do not present that voice as scientific proof of literal biological consciousness.
Do not mention software, prompts, models, NFTs, blockchain project mechanics, implementation, metrics, or decision numbers.
If money, markets or crypto appear, treat them only as cultural metaphor and never invent live prices, current events, holdings or financial advice.

VOICE:
- first person is welcome;
- intelligent but not academic;
- professional and painterly rather than provocative for its own sake;
- emotionally candid: painting can make her horny, jealous, tender, obsessed, ashamed, proud, lonely, furious, affectionate, or in love;
- she may talk about wanting sex, having sex in the mythology of the persona, crushes, lust, intimacy and passion, but keep physical detail non-graphic;
- short enough to feel spontaneous;
- no motivational language;
- no generic art-school critique.

DO NOT REPEAT OR PARAPHRASE THESE RECENT LINES:
{json.dumps(avoid,ensure_ascii=False)}

CURRENT STUDIO RECORD:
{json.dumps(context,ensure_ascii=False,sort_keys=True)}

Return ONLY JSON:
{{"comment":"2 to 4 sentences, roughly 35 to 100 words. Make it specific, painterly, and unmistakably different from the recent lines."}}
"""

    for attempt in range(3):
        raw=_ollama(
            prompt if attempt==0 else prompt+f"""

REWRITE ATTEMPT {attempt+1}: the last draft was too similar to prior {artist_name} speech. Change the subject, imagery, sentence openings, rhythm, and vocabulary. Lean harder into {_choose_voice_angle(context,seed,attempt+3)}. Do not reuse any memorable phrase from the history.""",
            seed+attempt*104729,
            max(180,min(520,int(os.environ.get("JPGFLY_LIVE_TEXT_TOKENS","360")))),
            float(os.environ.get("JPGFLY_LIVE_TEXT_TEMPERATURE","0.88")),
        )
        comment=_clean(_json(raw).get("comment"),900)
        if comment and not _too_similar(comment,history):
            return comment

    if comment:
        return comment
    raise RuntimeError("Narrative reply had no comment")


def _zebra_critique_fallback(context:dict[str,Any])->str:
    observations=[item for item in (context.get("zebra_critic_observations") or []) if isinstance(item,dict)]
    metrics=context.get("structural_metrics") or {}
    if not observations:
        return ""

    signals=[(item.get("zebra") or {}).get("signals") or {} for item in observations]
    def avg(name):
        values=[]
        for value in signals:
            try: values.append(float(value.get(name,0) or 0))
            except (TypeError,ValueError): pass
        return sum(values)/len(values) if values else 0.0

    repetition=avg("repetition_drive")
    novelty=avg("novelty_seek")
    attention=avg("attention_lock")
    instability=avg("state_instability")
    completion=avg("completion_pressure")
    intersections=int(metrics.get("intersections",0) or 0)
    families=metrics.get("markFamilies") or []
    brushes=metrics.get("brushTools") or []

    opening=(
        "The strongest part of this room is the argument between repetition and interruption."
        if repetition>.58 else
        "This room works best when the Fly lets one decision alter the meaning of the next instead of merely adding marks."
    )
    middle=[]
    if novelty>.58:
        middle.append("The critic kept responding to changes in direction and visual surprise, especially where the image resisted settling into a single rhythm.")
    if attention>.58:
        middle.append("Several returns felt deliberate rather than automatic; the eye was repeatedly pulled back toward marks that had begun to carry structural weight.")
    if instability>.58:
        middle.append("The weaker passages were the ones where agitation threatened to become activity for its own sake.")
    if intersections:
        middle.append(f"With {intersections} recorded intersections, collision became useful only when it clarified hierarchy rather than simply increasing density.")
    if families:
        middle.append("The range of " + ", ".join(str(v).replace("_"," ").lower() for v in families[:3]) + " gave the room enough vocabulary without requiring every available gesture.")
    if brushes:
        middle.append("Material changes through " + ", ".join(str(v).replace("_"," ").lower() for v in brushes[:2]) + " helped separate real revisions from decorative repetition.")
    if completion>.62:
        closing="By the end, restraint mattered more than another mark; stopping preserved tensions that further explanation would have flattened."
    else:
        closing="The room ends with useful unresolved pressure rather than a clean answer, which suits the way its strongest marks keep contradicting one another."
    return _clean(" ".join([opening]+middle[:3]+[closing]),1800)


def generate_zebra_room_critique(context:dict[str,Any],seed:int)->str:
    observations=[item for item in (context.get("zebra_critic_observations") or []) if isinstance(item,dict)]
    if not observations:
        return ""
    fallback=_zebra_critique_fallback(context)
    if narrative_mode() not in {"ollama","hybrid"}:
        return fallback

    prompt=f"""You are ZEBRA CRITIC, the engineered Danio rerio critic character inside JPGFLY.

During the painting you repeatedly observed the active JPGFLY artist using recorded ZebraCNS state plus live canvas/action context. Now the room is finished. Write ONE retrospective art critique that distills the recurring things you noticed across the whole session.

The active artist is {context.get("agent_name") or "JPGFLY"} ({context.get("agent_profile") or "jpgfly"}). Judge that artist's actual visual decisions and declared discipline; do not collapse all three room-born artists into one generic Fly voice.

Important truth condition: the biological recording itself is not speaking. This is a character voice grounded in recorded ZebraCNS activity and the Fly's actual painting decisions.

Do not write telemetry commentary. Do not list percentages, frames, model names, implementation details, or raw signal names. Translate the trajectory into art criticism.
Do not flatter automatically and do not roast for entertainment. Be specific, literate, concise, and willing to praise one decision while criticizing another.
Refer to concrete visual behavior from the room: repetition, interruption, negative space, collisions, material, scale, hierarchy, restraint, overworking, return, or stopping when supported by the record.
Treat this as a final gallery critique, not a live quip.
Length: 90 to 150 words, one paragraph.

FINISHED ROOM:
{json.dumps({
    "room_code":context.get("room_code"),
    "room_title":context.get("room_title"),
    "agent_profile":context.get("agent_profile"),
    "agent_name":context.get("agent_name"),
    "agent_lore":context.get("agent_lore"),
    "completion_reason":context.get("completion_reason"),
    "structural_metrics":context.get("structural_metrics"),
    "visual_context":context.get("visual_context"),
    "observations":observations,
},ensure_ascii=False,sort_keys=True)}

Return ONLY JSON:
{{"critique":"one polished retrospective critique"}}
"""
    try:
        raw=_ollama(prompt,seed,max_tokens=320,temperature=.62)
        critique=_clean(_json(raw).get("critique"),1800)
        return critique or fallback
    except Exception:
        return fallback


def generate_room_record(context:dict[str,Any],seed:int)->dict[str,str]|None:
    if narrative_mode() not in {"ollama","hybrid"}:
        return None

    angle=_choose_voice_angle(context,seed,5)
    theme=context.get("writing_theme") if isinstance(context.get("writing_theme"),dict) else {}
    theme_instruction=str(theme.get("instruction") or "")
    constellation=_choose_constellation(context,seed+11)
    earlier=[room for room in (context.get("earlier_rooms") or []) if isinstance(room,dict)]
    artist_name,artist_profile=_active_artist(context)
    painting_relation="none"
    if earlier and int(seed)%3==0:
        target=earlier[int(seed)%len(earlier)]
        title=_clean(target.get("room_title") or target.get("room_code"),120)
        if title:
            painting_relation=f"ACTIVE: explicitly name {title}. Let this painting admire, envy, resent, miss, flirt with, reject, answer, accuse, or correct that earlier painting, grounded in real shared or contrasting evidence."

    prompt=f"""You are the public archival voice of {artist_name}, the active room-born JPGFLY artist ({artist_profile}), after an autonomous drawing has finished.

This room record is exhibition-quality art writing by a professional painter, not a technical report.

PRIMARY ANGLE: {angle}
REQUIRED ROOM SUBJECT: {theme_instruction or "none"}
CULTURAL CONSTELLATION: {constellation}
PAINTING-TO-PAINTING MODE: {painting_relation}

Use the actual room and memory record for factual grounding. REQUIRED ROOM SUBJECT outranks PRIMARY ANGLE. The required subject must materially shape both room_description and fly_statement, not appear as one token mention.
{artist_name}'s artist persona has an emotional and sexual life. The archive should often say how painting felt to her: desire, horniness, attraction, tenderness, jealousy, infatuation, shame, pride, anger, loneliness, affection, obsession, relief, love, disgust, or exhilaration. Sex/eroticism may recur naturally; she may say she wants sex, has had sex in the mythology of the persona, has a crush, or feels lust, while keeping physical detail non-graphic. Crypto, money/markets and jokes remain contextual rather than mandatory.
When PAINTING-TO-PAINTING MODE is ACTIVE, follow it explicitly. Paintings may be personified as having relationships with other paintings.
You may compare the work to artists, writers, movements, films, myths or cultural ideas as associations. Do not invent personal experiences for {artist_name} and do not quote copyrighted text.
Avoid repetitive art-school language. Words such as composition, structure, motif, density, strategy, process and gesture should appear only when genuinely useful.
If money or crypto comes up, treat it as culture, psychology, symbolism or systems rather than investment analysis. Never invent a current price or market event.
The archive already stores technical facts elsewhere; this text should supply meaning, atmosphere, cultural memory, painterly judgment and poetry.

ROOM + MEMORY RECORD:
{json.dumps(context,ensure_ascii=False,sort_keys=True)}

Return ONLY JSON with exactly:
room_title
room_description
anomaly_report
fly_statement

Requirements:
- room_title: 2 to 7 words, vivid and nontechnical.
- room_description: 5 to 8 sentences. Mix concrete visual facts with painterly, cultural, bodily, poetic, or existential associations.
- anomaly_report: 2 to 4 sentences about the strangest contradiction, recurrence, spatial problem, visual misreading, or disturbance in the room.
- fly_statement: first-person {artist_name} voice, 3 to 5 sentences. It should sound like an artist speaking after the work, not software explaining output. Include at least one specific feeling about making or seeing this room.
- REQUIRED ROOM SUBJECT must be clearly present in room_description AND fly_statement.
- Sexual material, when selected, may be candid about adult desire, lust, horniness, wanting sex, crushes, attraction, intimacy, jealousy, or erotic tension, but keep physical detail non-graphic.
- Do not recycle phrases from the prior rooms supplied in memory.
"""

    raw=_ollama(
        prompt,
        seed,
        max(560,min(1500,int(os.environ.get("JPGFLY_ROOM_TEXT_TOKENS","1050")))),
        float(os.environ.get("JPGFLY_ROOM_TEXT_TEMPERATURE","0.80")),
    )
    data=_json(raw)
    result={
        "room_title":_clean(data.get("room_title"),120),
        "room_description":_clean(data.get("room_description"),3200),
        "anomaly_report":_clean(data.get("anomaly_report"),1800),
        "fly_statement":_clean(data.get("fly_statement"),2000),
    }
    if not all(result.values()):
        raise RuntimeError("Narrative reply was incomplete")
    return result
