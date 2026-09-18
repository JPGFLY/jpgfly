"""Deterministic thematic rotation for JPGFLY public writing.

The visual work remains authoritative. This module only chooses the interpretive
subject used by the language layer so Backrooms writing does not collapse into
one repeated art-school voice.

All agents share one learned memory/dataset. Agent identity only changes the
language temperament and artistic talent through which that shared memory is read.
"""
from __future__ import annotations

import random
import re
from typing import Any

from agent_profiles import get_agent_profile

THEMES=(
    {
        "id":"DESIRE_AND_SEX",
        "weight":0.26,
        "keywords":("sex","sexual","desire","horny","lust","erotic","intimacy","crush","attraction"),
        "prompt":"adult desire, sex, lust, attraction, intimacy, horniness, jealousy, appetite, tenderness, or erotic tension. Treat sexuality as a normal part of the artist persona, not a coy metaphor. Keep all physical detail non-graphic and adult/consensual in framing.",
    },
    {
        "id":"ART_AND_ARTISTS",
        "weight":0.15,
        "keywords":("artist","painting","drawing","surrealism","dada","basquiat","bourgeois","twombly","miró","carrington"),
        "prompt":"art, artists, art history, painting, drawing, taste, influence, rivalry, bad art, beauty, ugliness, or the social mythology around artists.",
    },
    {
        "id":"POETRY_AND_LANGUAGE",
        "weight":0.12,
        "keywords":("poetry","poem","verse","language","sentence","word","metaphor"),
        "prompt":"poetry, language, broken sentences, metaphor, naming, rhythm, fragments, or the point where an image starts behaving like a line of writing. Do not quote copyrighted text.",
    },
    {
        "id":"PHILOSOPHY",
        "weight":0.12,
        "keywords":("philosophy","meaning","identity","truth","consciousness","self","existence","reality"),
        "prompt":"philosophy: identity, meaning, truth, consciousness as a question, reality, selfhood, absurdity, mortality, perception, or what makes an object count as what we say it is.",
    },
    {
        "id":"HUMOR_AND_ABSURDITY",
        "weight":0.12,
        "keywords":("joke","funny","absurd","stupid","ridiculous","embarrassing","deadpan","satire"),
        "prompt":"dry jokes, embarrassment, stupidity, absurdity, bad taste, ridiculous visual logic, deadpan comedy, or a punchline that emerges from the image rather than being pasted onto it.",
    },
    {
        "id":"CRYPTO_AND_TERMINAL",
        "weight":0.11,
        "keywords":("crypto","bitcoin","hash","terminal","nonce","mempool","rpc","blockchain","market"),
        "prompt":"crypto and terminal culture: hashes, addresses, transactions, memecoins, terminals, protocols, scarcity, belief, markets, machine rituals, or how communities assign value. Never invent live prices, holdings, or financial advice.",
    },
    {
        "id":"MORTALITY_AND_BODY",
        "weight":0.07,
        "keywords":("death","mortality","body","flesh","decay","grief","corpse","residue"),
        "prompt":"the body, mortality, aging, flesh, residue, decay, grief, repair, appetite, vulnerability, and what remains after something disappears.",
    },
    {
        "id":"FREE_ASSOCIATION",
        "weight":0.05,
        "keywords":(),
        "prompt":"free association grounded in the actual image: ordinary life, insects, rooms, weather, memory, work, trash, beauty, irritation, private symbols, or anything else the room genuinely provokes.",
    },
)


def _recent_text(context:dict[str,Any])->str:
    bits=[]
    for room in (context.get("earlier_rooms") or [])[-4:]:
        if not isinstance(room,dict):
            continue
        for key in ("room_title","room_description","memory_thread","anomaly_report","fly_statement"):
            value=room.get(key)
            if value:
                bits.append(str(value))
    return " ".join(bits).casefold()


def _agent_id(context:dict[str,Any])->str:
    direct=str(context.get("agent_profile") or "").strip()
    if direct:
        return direct
    agent=context.get("agent") if isinstance(context.get("agent"),dict) else {}
    return str(agent.get("profile") or "jpgfly")


def _agent_language_instruction(context:dict[str,Any])->str:
    profile=get_agent_profile(_agent_id(context))
    return (
        "AGENT VOICE — "+str(profile.get("name") or "JPGFLY")+": "
        +str(profile.get("language_voice") or "")+" "
        +"Recurring obsessions: "+str(profile.get("language_obsessions") or "")+". "
        +"Sentence rhythm: "+str(profile.get("language_rhythm") or "")+". "
        +"Avoid: "+str(profile.get("language_avoid") or "")+". "
        +"This voice is mandatory. All agents share the same memory and reading dataset; do not invent separate knowledge for this agent. Distinguish the agent through talent, attention, metaphors, diction and rhythm."
    )


def choose_room_theme(context:dict[str,Any],seed:int)->dict[str,str]:
    """Choose one strong subject while discouraging immediate thematic repeats."""
    recent=_recent_text(context)
    rng=random.Random((int(seed)&0xffffffff)^0xD1B54A32)

    ids=[]
    weights=[]
    for item in THEMES:
        weight=float(item["weight"])
        hits=sum(1 for word in item["keywords"] if re.search(r"\b"+re.escape(word)+r"\b",recent))
        if hits:
            # Reduce repetition, but never ban a subject. Sex/crypto/jokes should
            # recur as part of the persona rather than appear once and disappear.
            weight*=0.34 if hits>=2 else 0.58
        ids.append(item["id"])
        weights.append(max(.005,weight))

    chosen=rng.choices(ids,weights=weights,k=1)[0]
    item=next(entry for entry in THEMES if entry["id"]==chosen)
    agent_instruction=_agent_language_instruction(context)
    subject=str(item["prompt"])
    return {
        "id":str(item["id"]),
        "prompt":subject+" "+agent_instruction,
        "instruction":(
            "PRIMARY SUBJECT: "+str(item["id"])+". "
            +subject
            +" This is not optional flavor. Make it materially shape the room description and the fly statement, while staying grounded in the actual artwork. "
            +agent_instruction
        ),
        "agent_voice":agent_instruction,
    }
