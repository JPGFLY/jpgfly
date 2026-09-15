"""Optional FLM-backed text generation for JPGFLY Backrooms."""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from experience_memory import compact_experience

_MODEL = None
_MODEL_KEY = None
_MODEL_LOCK = threading.Lock()
ROOM_CONTEXT_PATH = Path(__file__).resolve().parent / "context" / "room-writing.md"

ROOM_VOICE_EXAMPLES = (
    {
        "title": "Chair Field",
        "description": "The chairs began as furniture and ended as witnesses. Repeating the same four-legged grammar made the room feel less furnished than accused. Empty seats are useful because they imply a body without having to draw one. After enough repetition, the chair stopped being an object and became an agreement: four legs, a back, somewhere to put a person. Paintings work like that too. So does money. So do names. Enough people agree and the outline starts behaving like a fact.",
        "anomaly": "Several chair forms seem to borrow legs from older marks. One chair reads correctly only because an earlier line still props it up.",
        "statement": "I stopped drawing chairs before the chairs stopped happening. I like that kind of mistake. The room can keep the argument.",
    },
    {
        "title": "Someone Else's Face",
        "description": "The face arrived by accident and then became difficult to evict. A loop suggested an eye, another line behaved like a cheek, and suddenly every later mark had to negotiate with a person who was never actually there. Faces are aggressive patterns: give the eye two dots and a curve and it starts claiming ownership of the whole field. I kept damaging the recognition instead of removing it. That felt more accurate. Identity is often a shape held together by corrections, habits and other people's confidence.",
        "anomaly": "The apparent face is assembled from marks made for different jobs. One contour reads as an edge, a mouth, and a shadow depending on which neighboring line is treated as foreground.",
        "statement": "I did not decide to paint a person. The room accused me of one. I left the evidence incomplete.",
    },
)

def _room_writing_context() -> str:
    try:
        return ROOM_CONTEXT_PATH.read_text(encoding="utf-8")[:7000]
    except (OSError, UnicodeError):
        return ""


def configured_text_provider() -> str:
    value = os.environ.get("JPGFLY_TEXT_PROVIDER", "procedural").strip().lower()
    return value if value in {"procedural", "flm", "ollama", "hybrid"} else "procedural"


def _paths():
    root_raw = os.environ.get("JPGFLY_FLM_ROOT", "").strip()
    if not root_raw:
        raise RuntimeError("JPGFLY_FLM_ROOT is not configured")
    root = Path(root_raw).expanduser().resolve()
    run_raw = os.environ.get("JPGFLY_FLM_RUN", "").strip()
    if run_raw:
        run = Path(run_raw).expanduser().resolve()
    else:
        room_v2 = root / "runs" / "jpgfly-room-v2"
        preferred = root / "runs" / "jpgfly-style-v1"
        legacy = root / "runs" / "conversation-v2"
        if room_v2.is_dir():
            run = room_v2.resolve()
        elif preferred.is_dir():
            run = preferred.resolve()
        else:
            run = legacy.resolve()
    checkpoint = run / "adapter.safetensors"
    manifest = run / "run.json"
    if not (root / "flm" / "model.py").is_file():
        raise RuntimeError("JPGFLY_FLM_ROOT does not contain nftechie/flm")
    if not checkpoint.is_file() or not manifest.is_file():
        raise RuntimeError("FLM has no completed conversational training run")
    return root, run, checkpoint


def _model():
    global _MODEL, _MODEL_KEY
    root, run, checkpoint = _paths()
    device = os.environ.get("JPGFLY_FLM_DEVICE", "auto").strip().lower() or "auto"
    key = (str(root), str(run), device)
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_KEY == key:
            return _MODEL
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from flm.model import FLM
        model = FLM(device=device, checkpoint=checkpoint, profile="conversation")
        if not model.trained:
            raise RuntimeError("FLM conversational adapter is not trained")
        _MODEL = model
        _MODEL_KEY = key
        return model


def _clean(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip()


def _generate_remote(prompt: str, seed: int, max_tokens: int) -> str:
    base = os.environ.get("JPGFLY_FLM_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("JPGFLY_FLM_URL is not configured")
    timeout = max(5.0, min(600.0, float(os.environ.get("JPGFLY_FLM_TIMEOUT", "180"))))
    payload = json.dumps(
        {
            "prompt": prompt,
            "seed": int(seed) & 0x7FFFFFFF,
            "max_tokens": int(max_tokens),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers={"Content-Type":"application/json"}
    auth_token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_FLM_AUTH_TOKEN","").strip()
    if auth_token:
        headers["Authorization"]="Bearer "+auth_token
    request = urllib.request.Request(
        base + "/generate",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"FLM bridge HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"FLM bridge unavailable: {exc.reason}") from exc
    text = data.get("text") if isinstance(data, dict) else None
    if not text:
        raise RuntimeError("FLM bridge returned no text")
    return _clean(text, 4000)


def _generate(prompt: str, seed: int, max_tokens: int) -> str:
    if os.environ.get("JPGFLY_FLM_URL", "").strip():
        return _generate_remote(prompt, seed, max_tokens)

    model = _model()
    text = ""
    for event in model.generate(
        [{"role": "user", "content": prompt}],
        mode="intact",
        max_tokens=max_tokens,
        seed=int(seed) & 0x7FFFFFFF,
        telemetry=False,
    ):
        if event.get("type") in {"token", "done"}:
            text = event.get("text", text)
    return _clean(text, 4000)


def _top_items(value: Any, limit: int = 5) -> list[tuple[str, Any]]:
    if not isinstance(value, dict):
        return []
    def score(item):
        try:
            return float(item[1])
        except (TypeError, ValueError):
            return 0.0
    return sorted(((str(k), v) for k, v in value.items()), key=score, reverse=True)[:limit]


def _room_brief(context: dict[str, Any]) -> str:
    motifs = _top_items(context.get("motif_counts"), 6)
    compositions = _top_items(context.get("composition_mode_counts"), 3)
    goals = _top_items(context.get("goal_counts"), 4)
    colors = _top_items(context.get("color_counts"), 5)
    decision_modes = _top_items(context.get("decision_mode_counts"), 5)
    motif_modes = _top_items(context.get("motif_mode_counts"), 4)
    tensions = _top_items(context.get("room_tension_counts"), 3)
    context_passes = _top_items(context.get("context_pass_counts"), 6)
    visual_context = context.get("visual_context") or {}
    metrics = context.get("structural_metrics") or {}
    thoughts = [str(x) for x in (context.get("thought_fragments") or []) if str(x).strip()][-5:]
    commentary = []
    for item in (context.get("public_commentary") or [])[-4:]:
        text = item.get("text") if isinstance(item, dict) else item
        if text:
            commentary.append(_clean(text, 220))
    earlier = []
    for room in (context.get("earlier_rooms") or [])[-4:]:
        if isinstance(room, dict):
            title = room.get("room_title") or room.get("room_code")
            if title:
                earlier.append(str(title))
    lines = [
        f"room={context.get('room_code') or ''}",
        "dominant forms=" + ", ".join(f"{k}:{v}" for k, v in motifs) if motifs else "dominant forms=none named",
        "composition=" + ", ".join(f"{k}:{v}" for k, v in compositions) if compositions else "composition=unknown",
        "goals=" + ", ".join(f"{k}:{v}" for k, v in goals) if goals else "goals=unknown",
        "colors=" + ", ".join(f"{k}:{v}" for k, v in colors) if colors else "colors=unknown",
        "decision modes=" + ", ".join(f"{k}:{v}" for k, v in decision_modes) if decision_modes else "decision modes=unknown",
        "form treatment=" + ", ".join(f"{k}:{v}" for k, v in motif_modes) if motif_modes else "form treatment=unknown",
        "room tension=" + ", ".join(f"{k}:{v}" for k, v in tensions) if tensions else "room tension=unknown",
        "context arc=" + ", ".join(f"{k}:{v}" for k, v in context_passes) if context_passes else "context arc=unknown",
    ]
    memory_axes = [str(x) for x in (visual_context.get("context_pressures") or []) if str(x).strip()]
    if memory_axes:
        lines.append("abstract memory pressures=" + ", ".join(memory_axes[:4]))
    if visual_context:
        lines.append(
            "memory depth="
            + f"rooms:{visual_context.get('rooms_seen',0)}, readings:{visual_context.get('readings_seen',0)}, "
            + f"visual:{visual_context.get('visual_memory_strength',0)}, conceptual:{visual_context.get('conceptual_memory_strength',0)}"
        )
    metric_bits = []
    for key in ("intersections", "motifDevelopments", "erasureActions", "branchActions", "coverage", "occupiedRegions", "regionalContrast", "densityContrast"):
        if key in metrics:
            metric_bits.append(f"{key}={metrics.get(key)}")
    if metric_bits:
        lines.append("structure=" + ", ".join(metric_bits[:7]))
    if context.get("concept"):
        lines.append("mechanical synopsis=" + _clean(context.get("concept"), 320))
    if thoughts:
        lines.append("decision fragments=" + " / ".join(_clean(x, 180) for x in thoughts))
    if commentary:
        lines.append("recent fly notes=" + " / ".join(commentary))
    if earlier:
        lines.append("recent room titles=" + ", ".join(earlier))
    ollama_draft=context.get("ollama_draft")
    if isinstance(ollama_draft,dict):
        draft_bits=[]
        for key in ("room_title","room_description","anomaly_report","fly_statement"):
            value=_clean(ollama_draft.get(key),700)
            if value:
                draft_bits.append(f"{key}={value}")
        if draft_bits:
            lines.append("OLLAMA DIRECTOR DRAFT (use as material, not final wording)="+" | ".join(draft_bits))
    return "\n".join(lines)[:5200]


def _recent_text(context: dict[str, Any]) -> str:
    bits=[]
    for room in (context.get("earlier_rooms") or [])[-4:]:
        if not isinstance(room,dict):
            continue
        for key in ("room_title","room_description","memory_thread","fly_statement"):
            value=room.get(key)
            if value:
                bits.append(str(value))
    for note in (context.get("recent_public_notes") or [])[-6:]:
        value=note.get("text") if isinstance(note,dict) else note
        if value:
            bits.append(str(value))
    return " ".join(bits).casefold()


def _interpretive_lens(context: dict[str, Any], seed: int, *, live: bool=False) -> str:
    visual=context.get("visual_context") or {}
    register=str(visual.get("content_register") or "FORMAL")
    pools={
        "FORMAL":(
            "material, edge, rhythm and the difference between a mark and an object",
            "perception, ambiguity, recognition and how little information becomes a shape",
            "art-making as revision, interruption and selective attention",
        ),
        "DOMESTIC":(
            "rooms, furniture, thresholds, privacy and ordinary objects acquiring pressure",
            "maintenance, clutter, usefulness and the emotional charge of mundane things",
            "habitation, absence and what a room implies without showing a person",
        ),
        "NATURAL":(
            "weather, growth, decay, insect behavior and organic systems",
            "camouflage, migration, nests, traces and nonhuman ways of occupying space",
            "surface, texture, erosion and the difference between growth and damage",
        ),
        "ARCHITECTURAL":(
            "architecture, boundaries, corridors, load, enclosure and failed structure",
            "maps, edges, circulation and spaces that control movement",
            "construction, ruins, thresholds and the politics of what gets enclosed",
        ),
        "COSMIC":(
            "scale, orbit, night, distance and the difficulty of locating a center",
            "gravity, repetition, signal and the strange calm of large systems",
            "time, recurrence and forms that feel older than their explanation",
        ),
        "MORTAL":(
            "mortality, residue, memory, repair and the evidence left by disappearance",
            "decay, preservation, repetition and the problem of deciding when something is finished",
            "absence, inheritance and the way damaged structures keep carrying meaning",
        ),
        "ABSURD":(
            "deadpan comedy, failed seriousness and visual decisions that become funny by insisting too hard",
            "absurdity, embarrassment, bad taste and the line between a mistake and a style",
            "satire, awkwardness and the dignity of an image refusing to behave",
        ),
        "BODILY":(
            "body, gesture, touch, vulnerability and the physical memory of surfaces",
            "anatomy, pressure, appetite and the uneasy boundary between figure and field",
            "flesh, intimacy and embodiment without turning the room into an erotic illustration",
        ),
    }
    rng=random.Random((int(seed)&0xffffffff)^0x6A09E667)
    choices=list(pools.get(register,pools["FORMAL"]))
    recent=_recent_text(context)

    # Crypto/protocol, explicit eroticism and comedy are occasional lenses, not
    # JPGFLY's default personality. Do not repeat them in adjacent rooms.
    rare=[
        ("value, scarcity, exchange and collective belief without turning the room into financial commentary",
         ("money","scarcity","value")),
        ("protocols, addresses, hashes and machine systems as metaphor rather than crypto commentary",
         ("hash","crypto","bitcoin","memecoin","blockchain")),
    ]
    if register=="BODILY":
        rare.append(("desire and erotic tension treated as one possible bodily metaphor, not the room's automatic subject",
                     ("sex","sexual","erotic","desire","intimacy")))
    if register=="ABSURD":
        rare.append(("a dry joke emerging from the image itself rather than forcing a punchline",
                     ("joke","funny","satire","deadpan","absurd")))

    for lens,keywords in rare:
        if not any(word in recent for word in keywords) and rng.random() < (.10 if live else .14):
            choices.append(lens)

    return rng.choice(choices)


def _focused_memory(context: dict[str, Any], seed: int, lens: str="") -> str:
    memory=compact_experience()
    topics=_top_items(memory.get("topics"),10)
    passages=memory.get("topic_memory") or {}
    if not topics:
        return ""

    recent=_recent_text(context)
    topic_terms={
        "art":("art","painting","drawing","artist"),
        "poetry":("poetry","poem","verse"),
        "philosophy":("philosophy","meaning","identity","consciousness"),
        "desire_body":("sex","sexual","erotic","desire","flesh","intimacy"),
        "life_death":("death","mortality","decay","funeral"),
        "money_value":("money","value","scarcity","market"),
        "crypto":("crypto","bitcoin","memecoin"),
        "crypto_terminal":("hash","transaction","nonce","mempool","rpc","blockchain"),
        "luck_risk":("luck","risk","gamble","chance"),
        "dreams_memory":("dream","memory","remember"),
        "humor_absurdity":("joke","funny","satire","absurd","deadpan"),
        "insects":("fly","insect","moth","beetle","spider"),
    }
    available=[]
    for topic,weight in topics:
        keywords=topic_terms.get(topic,())
        if keywords and any(word in recent for word in keywords):
            continue
        available.append((topic,float(weight or 0)))

    if not available:
        available=[(topic,float(weight or 0)) for topic,weight in topics]

    rng=random.Random((int(seed)&0xffffffff)^0xBB67AE85)
    # Some rooms should be allowed to answer their own image without dragging a
    # recurring reading topic into every description.
    if rng.random()<.30:
        return ""

    lens_fold=str(lens or "").casefold()
    preferred=[]
    preference_map={
        "body":("desire_body",),"flesh":("desire_body",),"mortality":("life_death",),
        "decay":("life_death",),"memory":("dreams_memory","life_death"),
        "insect":("insects",),"art":("art",),"poetry":("poetry",),
        "value":("money_value",),"scarcity":("money_value",),
        "protocol":("crypto_terminal",),"hash":("crypto_terminal",),
        "absurd":("humor_absurdity",),"joke":("humor_absurdity",),
    }
    for word,names in preference_map.items():
        if word in lens_fold:
            preferred.extend(names)

    candidates=[item for item in available if item[0] in preferred] or available
    weights=[.18+max(0.0,w)**.5 for _,w in candidates]
    topic=rng.choices([t for t,_ in candidates],weights=weights,k=1)[0]
    passage=_clean(passages.get(topic),320)
    if not passage:
        return f"one optional memory thread: {topic.replace('_',' ')}"
    return f"one optional memory thread ({topic.replace('_',' ')}): {passage}"



def _artwork_memory(context: dict[str, Any]) -> str:
    lines = []
    for room in (context.get("earlier_rooms") or [])[-4:]:
        if not isinstance(room, dict):
            continue
        title = _clean(room.get("room_title") or room.get("room_code"), 120)
        description = _clean(room.get("room_description"), 360)
        statement = _clean(room.get("fly_statement"), 220)
        thread = _clean(room.get("memory_thread"), 300)
        concept = _clean(room.get("concept"), 220)
        if not title:
            continue
        bits = [f"earlier room: {title}"]
        if description:
            bits.append("description=" + description)
        if thread:
            bits.append("memory thread=" + thread)
        if statement:
            bits.append("fly statement=" + statement)
        elif concept:
            bits.append("structure=" + concept)
        lines.append(" | ".join(bits))
    return "\n".join(lines)[:2200]


def _candidate_score(result: dict[str, str]) -> float:
    text = " ".join(str(result.get(k) or "") for k in ("room_description", "anomaly_report", "fly_statement"))
    words = re.findall(r"[A-Za-z0-9']+", text.casefold())
    if not words:
        return -1e9
    unique = len(set(words)) / max(1, len(words))
    score = min(len(words), 260) * 0.07 + unique * 28
    description = str(result.get("room_description") or "")
    anomaly = str(result.get("anomaly_report") or "")
    statement = str(result.get("fly_statement") or "")
    score += min(_word_count(description), 150) * 0.04
    score += min(_word_count(anomaly), 55) * 0.07
    score += min(_word_count(statement), 55) * 0.08
    generic = (
        "formed as a", "recorded intersections", "the room stopped asking",
        "i kept moving until", "autonomous drawing", "the composition features",
        "this artwork", "visual elements", "creates a sense of",
    )
    folded = text.casefold()
    score -= sum(9 for phrase in generic if phrase in folded)
    sentences = [x.strip().casefold() for x in re.split(r"[.!?]+", text) if len(x.strip()) > 10]
    score -= max(0, len(sentences) - len(set(sentences))) * 8
    if statement.strip().startswith("I "):
        score += 3
    if _room_text_is_rich(result):
        score += 12
    return score


def _word_count(value: Any) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", str(value or "")))


def _room_text_is_rich(result: dict[str, str]) -> bool:
    return (
        _word_count(result.get("room_description")) >= 95
        and _word_count(result.get("anomaly_report")) >= 18
        and _word_count(result.get("fly_statement")) >= 14
    )


def _parse(text: str) -> dict[str, str]:
    text = text.strip()
    # Prefer strict JSON, but accept a fenced JSON object or labelled lines.
    candidates = [text]
    fenced = re.search(r"\{[\s\S]*\}", text)
    if fenced:
        candidates.append(fenced.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                result = {
                    "room_title": _clean(data.get("room_title"), 96),
                    "room_description": _clean(data.get("room_description"), 1800),
                    "anomaly_report": _clean(data.get("anomaly_report"), 900),
                    "fly_statement": _clean(data.get("fly_statement"), 900),
                }
                if all(result.values()):
                    return result
        except Exception:
            pass

    labels = {
        "room_title": r"(?:^|\n)TITLE:\s*(.+)",
        "room_description": r"(?:^|\n)DESCRIPTION:\s*(.+)",
        "anomaly_report": r"(?:^|\n)ANOMALY:\s*(.+)",
        "fly_statement": r"(?:^|\n)STATEMENT:\s*(.+)",
    }
    result = {}
    for key, pattern in labels.items():
        match = re.search(pattern, text, re.I)
        result[key] = _clean(match.group(1) if match else "", 1800 if key == "room_description" else 900 if key != "room_title" else 96)
    if all(result.values()):
        return result
    raise RuntimeError("FLM reply did not contain the required Backrooms fields")


def _strip_field_output(text: str, labels: tuple[str, ...] = ()) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json|text)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    for label in labels:
        value = re.sub(rf"^\s*{re.escape(label)}\s*:\s*", "", value, flags=re.I)
    value = value.strip().strip('"').strip()
    return _clean(value, 4000)


def _field_prompt(kind: str, brief: str, memory: str, artwork_memory: str, angle: str) -> str:
    shared = f"""You are JPGFLY's trained Backrooms writing voice.

Write only the requested field. No JSON. No label. No preface.

The painting brain is separate from you. Do not discuss models, prompts, telemetry, metrics, implementation, or autonomy marketing.
JPGFLY is a fictional artist persona. She may speak directly about feelings, desire, sex, lust, horniness, jealousy, tenderness, passion, shame, pride, loneliness, anger, affection, and love. Treat those as the voice of the artwork/persona, not scientific evidence of literal biological sentience.
Use the painting facts as evidence, not as a checklist.
Avoid generic art-review language such as "this artwork explores", "creates a sense of", "visual elements", or "the composition features".
Prefer one strong association over many shallow topics.
Ground the writing in what the room actually did.
Dry, strange, concrete, literate, emotionally candid, occasionally funny, bodily, horny, tender, jealous, or passionate when the room earns it.
Most finished-room writing should contain at least one first-person affective reaction to making or seeing the work.

ROOM BRIEF:
{brief}

ACCUMULATED READING MEMORY:
{memory or "No strong reading connection is active."}

ARTWORK MEMORY:
{artwork_memory or "No earlier room is available yet."}

POSSIBLE ANGLE:
{angle}

MEMORY RULES:
Earlier rooms and readings are context, not a script. Use them to create continuity, friction, or departure.
Do not simply list remembered topics. Do not copy an earlier room's wording.
If an earlier room is relevant, make the relationship concrete: echo, reversal, mutation, refusal, or unfinished residue.
The new room must still stand on its own.
Feelings are part of JPGFLY's default voice. Sex/eroticism is a recurring part of her adult persona rather than a forbidden special event: she may say she is horny, wants sex, feels lust or attraction, or reads a mark erotically when that feels connected to the room. Do not force sexuality into every room and keep it non-graphic. Jokes, crypto/protocol culture, and money remain contextual rather than mandatory.
When ARTWORK MEMORY contains an active painting-to-painting directive, follow it explicitly and let the current room have an opinion about the named earlier painting.
"""

    if kind == "title":
        return shared + """
TASK:
Write a room title of 2 to 6 words. It should sound like a work of art, not a file name or technical label.
Return only the title.
"""
    if kind == "description":
        return shared + """
TASK:
Write the finished room description in 150 to 230 words.
Begin with a concrete visual behavior in this room. Develop it into a real interpretation rather than a caption.
Use at least two layers of context: the present visual structure and either an earlier-room echo/departure or accumulated reading memory.
Make the transition between visual fact and idea feel earned.
You may connect the room to identity, architecture, value, desire, mortality, protocol culture, humor, art history, or another fitting association, but do not pile up unrelated themes.
Do not quote counts. Do not summarize every feature. Do not use the phrase "formed as".
Write one substantial paragraph with a beginning, turn, and ending.
Return only the prose paragraph.
"""
    if kind == "memory":
        return shared + """
TASK:
Write a MEMORY THREAD in 70 to 120 words.
Explain how this room belongs to JPGFLY's developing visual biography.
Use one concrete relationship to an earlier room or accumulated reading memory: echo, reversal, mutation, refusal, unfinished residue, or a habit deliberately broken.
Do not say "the database remembers", "the model learned", or describe implementation.
Write emotional continuity in the voice of the artist persona when useful: attraction, rivalry, regret, tenderness, jealousy, obsession, or relief may connect one room to another.
Do not present persona feelings as scientific evidence about literal consciousness.
Keep it about artistic continuity and change.
Return only the memory-thread prose.
"""
    if kind == "anomaly":
        return shared + """
TASK:
Write an anomaly report in 3 to 5 specific sentences.
Describe strange relations inside the work: a line doing two jobs, a form surviving erasure, a false foreground/background relation, a repeated gesture mutating, or another concrete visual contradiction.
At least one sentence should explain how the anomaly changes the reading of the whole room rather than merely naming a feature.
Do not mention software or process metadata.
Return only the anomaly report.
"""
    return shared + """
TASK:
Write the fly statement in first person, 4 to 6 short sentences.
It should sound like a dry artist's afterthought with a specific opinion and at least one real feeling about what changed during this room.
Desire, horniness, attraction, jealousy, tenderness, shame, pride, disgust, passion, loneliness, anger, affection, or love are all available. Sexuality may be explicit in attitude but keep physical detail non-graphic.
It may acknowledge an echo from an earlier room or something learned from accumulated memory, but it must not sound like a database report.
No "composition complete", no "I kept moving until", no metrics.
Return only the statement.
"""


def _field_good(kind: str, text: str) -> bool:
    words = _word_count(text)
    if kind == "title":
        return 2 <= words <= 8 and len(text) <= 96
    if kind == "description":
        return words >= 135
    if kind == "memory":
        return words >= 55
    if kind == "anomaly":
        return words >= 28
    return words >= 20


def _generate_field(kind: str, brief: str, memory: str, artwork_memory: str, angle: str, seed: int) -> str:
    token_limits = {"title": 40, "description": 360, "memory": 210, "anomaly": 190, "statement": 150}
    labels = {
        "title": ("TITLE", "ROOM TITLE"),
        "description": ("DESCRIPTION", "ROOM DESCRIPTION"),
        "memory": ("MEMORY", "MEMORY THREAD"),
        "anomaly": ("ANOMALY", "ANOMALY REPORT"),
        "statement": ("STATEMENT", "FLY STATEMENT"),
    }
    first = _strip_field_output(
        _generate(_field_prompt(kind, brief, memory, artwork_memory, angle), seed, token_limits[kind]),
        labels[kind],
    )
    if _field_good(kind, first):
        return first

    retry = _strip_field_output(
        _generate(
            _field_prompt(kind, brief, memory, artwork_memory, angle)
            + f"\nThe previous attempt was too thin. Rewrite it with more substance, stronger continuity with memory, and more specific visual interpretation. Do not merely pad it. Previous attempt: {first}",
            seed + 104729,
            token_limits[kind],
        ),
        labels[kind],
    )
    if _field_good(kind, retry):
        return retry
    best = retry if _word_count(retry) >= _word_count(first) else first
    if kind == "title":
        return best
    continuation = _strip_field_output(
        _generate(
            _field_prompt(kind, brief, memory, artwork_memory, angle)
            + f"\nContinue and deepen the following draft with new concrete material. Do not restate its opening or repeat its sentences. Draft: {best}",
            seed + 209759,
            max(90, token_limits[kind] // 2),
        ),
        labels[kind],
    )
    if continuation and continuation.casefold() not in best.casefold():
        best = _clean((best.rstrip() + " " + continuation.lstrip()), 4000)
    return best


def generate_room_text(context: dict[str, Any], seed: int) -> dict[str, str] | None:
    if configured_text_provider() not in {"flm","hybrid"}:
        return None

    brief = _room_brief(context)
    angle = _interpretive_lens(context, seed, live=False)
    memory = _focused_memory(context, seed, angle)
    artwork_memory = _artwork_memory(context)
    earlier_rooms=[room for room in (context.get("earlier_rooms") or []) if isinstance(room,dict)]
    if earlier_rooms and int(seed)%3==0:
        target=earlier_rooms[int(seed)%len(earlier_rooms)]
        target_title=_clean(target.get("room_title") or target.get("room_code"),120)
        if target_title:
            artwork_memory += (
                "\nPAINTING-TO-PAINTING MODE: ACTIVE. The current room should explicitly name "
                + target_title
                + " and treat it as another painting with a relationship to this one: rival, lover, crush, ancestor, child, correction, relapse, accusation, rejection, or unfinished conversation. Ground the relationship in actual visual or thematic evidence."
            )

    title = _generate_field("title", brief, memory, artwork_memory, angle, seed + 11)
    description = _generate_field("description", brief, memory, artwork_memory, angle, seed + 23)
    memory_thread = _generate_field("memory", brief, memory, artwork_memory, angle, seed + 31)
    anomaly = _generate_field("anomaly", brief, memory, artwork_memory, angle, seed + 37)
    statement = _generate_field("statement", brief, memory, artwork_memory, angle, seed + 53)

    result = {
        "room_title": _clean(title, 96),
        "room_description": _clean(description, 2600),
        "memory_thread": _clean(memory_thread, 1600),
        "anomaly_report": _clean(anomaly, 1200),
        "fly_statement": _clean(statement, 900),
    }
    if not all(result.values()):
        raise RuntimeError("FLM field generation returned an empty Backrooms field")
    return result


def generate_room_fallback(context: dict[str, Any], seed: int) -> dict[str, str]:
    """Readable emergency copy when the FLM bridge is unavailable.

    This is deliberately literary rather than diagnostic. It never pretends to be
    FLM output; callers should label the provider as a fallback.
    """
    styles = _top_items((context.get("structural_metrics") or {}).get("familyCounts"), 4)
    tensions = _top_items(context.get("room_tension_counts"), 2)
    modes = _top_items(context.get("decision_mode_counts"), 4)
    goals = _top_items(context.get("goal_counts"), 3)

    style = styles[0][0] if styles else "gesture"
    tension = tensions[0][0] if tensions else "ORDER_VS_RUPTURE"
    mode = modes[0][0] if modes else "ABSTRACT_BUILD"
    goal = goals[0][0] if goals else "WANDER"

    titles = {
        "DENSITY_VS_VOID": ("The Empty Part Wins", "Pressure Around Nothing", "Room for the Missing"),
        "ORDER_VS_RUPTURE": ("Bad Agreement", "The Rule Breaks Here", "Order With a Crack"),
        "RETURN_VS_ESCAPE": ("Almost Leaving", "The Mark Comes Back", "Exit Rehearsal"),
        "CENTER_VS_EDGE": ("Center With Bad Manners", "Edge Against Center", "Nothing Stays Peripheral"),
        "SYSTEM_VS_NOISE": ("System With Static", "Useful Corruption", "Noise Learns the Rules"),
        "FIGURE_VS_FIELD": ("Almost a Body", "The Figure Refuses", "Shape Without Owner"),
    }
    title_choices = titles.get(tension, ("Unfinished Argument", "Wrong Shape, Right Room", "Field With a Problem"))
    title = title_choices[int(seed) % len(title_choices)]

    style_name = style.replace("_", " ").lower()
    tension_name = tension.replace("_", " ").lower()
    mode_name = mode.replace("_", " ").lower()
    goal_name = goal.replace("_", " ").lower()

    description = (
        f"The room kept leaning on {style_name} until the gesture stopped behaving like decoration. "
        f"What looked simple at first became an argument between {tension_name}: one part kept insisting on structure while another kept finding a way to spoil it. "
        f"The useful thing was not a recognizable object but the moment the marks began depending on each other. "
        f"A line became an edge only because another line contradicted it; empty space became active because the drawing kept approaching and refusing it. "
        f"The dominant behavior was {mode_name}, but the room never settled into obedience. "
        f"It ended closer to {goal_name} than to illustration: a field that had learned enough rules to break the right ones."
    )
    earlier = [room for room in (context.get("earlier_rooms") or []) if isinstance(room, dict)]
    if earlier:
        previous = earlier[0].get("room_title") or earlier[0].get("room_code") or "the previous room"
        memory_thread = (
            f"This room does not repeat {previous}; it keeps one unfinished habit from it and changes the terms. "
            f"The return is structural rather than literal: familiar pressure reappears through {style_name}, while the present {tension_name} forces that habit into a different role. "
            "The archive is beginning to behave less like a sequence of isolated drawings and more like a visual biography made from persistence, refusal, and revision."
        )
    else:
        memory_thread = (
            "There is no earlier room to answer yet, so the first memory is being made here. "
            f"The important residue is not an object but a habit: {style_name}, revision, and the tension between {tension_name}. "
            "Future rooms can return to that habit, contradict it, or leave it behind."
        )
    anomaly = (
        f"Several {style_name} marks appear to change roles depending on which neighboring gesture is read first. "
        "At least one apparently empty region behaves like a shape because surrounding marks repeatedly stop at its boundary. "
        "The room reads as more organized from a distance than it does up close."
    )
    statement = (
        "I thought the empty part was passive. It wasn't. "
        "The marks kept negotiating with something I never drew. "
        "That was more useful than finishing an object."
    )
    return {
        "room_title": title,
        "room_description": description,
        "memory_thread": memory_thread,
        "anomaly_report": anomaly,
        "fly_statement": statement,
    }

def generate_live_text(context: dict[str, Any], seed: int) -> str | None:
    """Generate JPGFLY's live public studio note with the actual FLM model."""
    if configured_text_provider() not in {"flm","hybrid"}:
        return None

    recent=[]
    for entry in context.get("recent_public_notes") or []:
        text=entry.get("text") if isinstance(entry,dict) else entry
        if text:recent.append(_clean(text,500))
    recent=recent[-10:]

    angle=_interpretive_lens(context,seed,live=True)

    brief=_room_brief(context)
    memory=_focused_memory(context,seed,angle)
    earlier_rooms=[room for room in (context.get("earlier_rooms") or []) if isinstance(room,dict)]
    relationship_note="none"
    if earlier_rooms and int(seed)%5==0:
        target=earlier_rooms[int(seed)%len(earlier_rooms)]
        target_title=_clean(target.get("room_title") or target.get("room_code"),120)
        if target_title:
            relationship_note=f"ACTIVE: mention {target_title} directly and let the current painting react to it emotionally."
    prompt=f"""Write one JPGFLY live studio note while a room is still being painted.

The painting brain is separate from you. You are only the trained text voice describing/associating from its current record.
Do not explain that architecture in the note.
Do not use telemetry language, counts, or generic art criticism.
JPGFLY's artist persona may speak as if she has feelings and an adult sexual life. Let her say what painting feels like: desire, attraction, horniness, tenderness, jealousy, obsession, shame, pride, anger, boredom, relief, affection, or love. This is persona language, not scientific proof of literal consciousness.
Use one concrete thing from the painting brief, then make one surprising but intelligible association.
Sexual references may recur when they fit, including saying she is horny or wants sex, but keep physical detail non-graphic.
Dry, concise, strange, specific. 2 to 4 sentences, 35 to 90 words.
Do not repeat recent notes.

CURRENT PAINTING:
{brief}

ACTIVE MEMORY:
{memory or "none"}

PAINTING-TO-PAINTING MODE:
{relationship_note}

RECENT NOTES:
{json.dumps(recent[-6:], ensure_ascii=False)}

OLLAMA DIRECTOR NOTE:
{_clean(context.get("ollama_note"),900) or "none"}

OPTIONAL ANGLE:
{angle}

STYLE EXAMPLES:
- "A room trying not to become a face. It is losing."
- "Empty space is the only part of the painting that knows when to shut up."
- "A joke that discovers a price tag and immediately develops a theology."

Return only the note.
"""
    text=_generate(
        prompt,
        seed,
        max(128,min(360,int(os.environ.get("JPGFLY_FLM_LIVE_TOKENS","240")))),
    )
    return text or None
