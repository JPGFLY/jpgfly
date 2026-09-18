"""Sanitized adapter for the optional local ZebraCNS activity engine.

The local node may stream real zebrafish activity data (currently ZAPBench).
This adapter exposes only a bounded telemetry contract to the web process and
to the Fly Brain candidate selector. Biological source data and engineered
art/game mappings are kept explicitly separate.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.request
from urllib.parse import urlparse
from typing import Any

SIGNAL_KEYS=(
    "visual_salience","arousal","persistence","inhibition",
    "exploration","motor_left","motor_right",
    "novelty_seek","attention_lock","escape_drive","repetition_drive",
    "state_instability","completion_pressure","tempo",
)
ACTIONS={"LEFT","RIGHT","FORWARD","FREEZE","NONE"}
DEFAULT_LOCAL_URL="http://127.0.0.1:4770"
_CACHE_LOCK=threading.Lock()
_CACHE_AT=0.0
_CACHE_VALUE:dict[str,Any]|None=None


def _truthy(value:str|None)->bool:
    return str(value or "").strip().lower() in {"1","true","yes","on"}


def zebracns_enabled()->bool:
    return _truthy(os.environ.get("JPGFLY_ZEBRACNS_ENABLED")) or bool(os.environ.get("JPGFLY_ZEBRACNS_URL","").strip())


def _finite(value:Any,default:float=0.0)->float:
    try:
        number=float(value)
    except (TypeError,ValueError):
        return default
    return number if math.isfinite(number) else default


def _unit(value:Any)->float:
    return max(0.0,min(1.0,_finite(value)))


def _pair(value:Any,default:list[float])->list[float]:
    if not isinstance(value,(list,tuple)) or len(value)<2:
        return list(default)
    return [_unit(value[0]),_unit(value[1])]


def _backbone(enabled:bool,status:str)->dict[str,Any]:
    return {
        "ok":True,
        "enabled":enabled,
        "connected":False,
        "system":"ZebraCNS",
        "mode":"LOCAL-FIRST",
        "status":status,
        "dataset":"NONE",
        "source":"",
        "license":"",
        "activity_loaded":False,
        "biological_data_loaded":False,
        "connectome_loaded":False,
        "frame":0,
        "sampled_neurons":0,
        "total_neurons":0,
        "game":{
            "name":"ESCAPE TANK",
            "fish":[0.42,0.55],
            "food":[0.80,0.25],
            "predator":[0.18,0.74],
            "score":0,
            "episode":0,
        },
        "action":"NONE",
        "signals":{key:0.0 for key in SIGNAL_KEYS},
        "nodes":[],
        "note":"Backbone only. No real zebrafish activity data is loaded and no biological activity is being claimed.",
    }


def _sanitize_state(raw:Any)->dict[str,Any]:
    if not isinstance(raw,dict):
        raise ValueError("ZebraCNS state must be an object")

    signals_raw=raw.get("signals") if isinstance(raw.get("signals"),dict) else {}
    signals={key:_unit(signals_raw.get(key,0.0)) for key in SIGNAL_KEYS}

    game_raw=raw.get("game") if isinstance(raw.get("game"),dict) else {}
    game={
        "name":str(game_raw.get("name") or "ESCAPE TANK")[:80],
        "fish":_pair(game_raw.get("fish"),[0.42,0.55]),
        "food":_pair(game_raw.get("food"),[0.80,0.25]),
        "predator":_pair(game_raw.get("predator"),[0.18,0.74]),
        "score":int(_finite(game_raw.get("score"),0)),
        "episode":max(0,int(_finite(game_raw.get("episode"),0))),
    }

    action=str(raw.get("action") or "NONE").upper()
    if action not in ACTIONS:
        action="NONE"

    nodes=[]
    for item in (raw.get("nodes") or [])[:320]:
        if not isinstance(item,dict):
            continue
        node={
            "id":str(item.get("id") or item.get("body_id") or "")[:96],
            "x":_unit(item.get("x",0.5)),
            "y":_unit(item.get("y",0.5)),
            "activity":_unit(item.get("activity",item.get("spikes",0))),
        }
        if item.get("region") is not None:
            node["region"]=str(item.get("region"))[:80]
        nodes.append(node)

    activity_loaded=bool(raw.get("activity_loaded"))
    connectome_loaded=bool(raw.get("connectome_loaded"))
    biological_loaded=bool(raw.get("biological_data_loaded")) or activity_loaded or connectome_loaded

    return {
        "ok":True,
        "enabled":True,
        "connected":True,
        "system":"ZebraCNS",
        "mode":"LOCAL-FIRST",
        "status":str(raw.get("status") or "RUNNING")[:64],
        "dataset":str(raw.get("dataset") or "UNSPECIFIED LOCAL DATASET")[:160],
        "source":str(raw.get("source") or "")[:240],
        "license":str(raw.get("license") or "")[:80],
        "activity_loaded":activity_loaded,
        "biological_data_loaded":biological_loaded,
        "connectome_loaded":connectome_loaded,
        "frame":max(0,int(_finite(raw.get("frame"),0))),
        "sampled_neurons":max(0,int(_finite(raw.get("sampled_neurons"),0))),
        "total_neurons":max(0,int(_finite(raw.get("total_neurons"),0))),
        "game":game,
        "action":action,
        "signals":signals,
        "nodes":nodes,
        "note":str(raw.get("note") or "Local ZebraCNS telemetry.")[:420],
    }


def _endpoint()->tuple[str,dict[str,str],dict[str,Any]|None]:
    configured=os.environ.get("JPGFLY_ZEBRACNS_URL","").strip().rstrip("/")
    enabled=zebracns_enabled()
    if not enabled:
        return "",{},_backbone(False,"BACKBONE_ONLY")

    url=configured or DEFAULT_LOCAL_URL
    parsed=urlparse(url)
    loopback=(parsed.hostname or "").lower() in {"127.0.0.1","localhost","::1"}
    token=(os.environ.get("JPGFLY_ZEBRACNS_AUTH_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip() or os.environ.get("JPGFLY_CONTROL_TOKEN","").strip())

    if not loopback and len(token)<32:
        state=_backbone(True,"AUTH_REQUIRED")
        state["ok"]=False
        state["note"]="Remote ZebraCNS telemetry requires JPGFLY_ZEBRACNS_AUTH_TOKEN with at least 32 characters."
        return "",{},state

    headers={}
    if token:
        headers["authorization"]="Bearer "+token
    return url,headers,None


def public_zebracns_state(*,max_age:float=0.20)->dict[str,Any]:
    global _CACHE_AT,_CACHE_VALUE
    url,headers,terminal=_endpoint()
    if terminal is not None:
        return terminal

    now=time.monotonic()
    with _CACHE_LOCK:
        if _CACHE_VALUE is not None and now-_CACHE_AT<=max(0.0,float(max_age)):
            return json.loads(json.dumps(_CACHE_VALUE))

    try:
        request=urllib.request.Request(url+"/state",headers=headers)
        with urllib.request.urlopen(request,timeout=3) as response:
            value=_sanitize_state(json.load(response))
        with _CACHE_LOCK:
            _CACHE_AT=now
            _CACHE_VALUE=value
        return json.loads(json.dumps(value))
    except Exception:
        state=_backbone(True,"LOCAL_ENGINE_OFFLINE")
        state["ok"]=False
        state["note"]="ZebraCNS is enabled, but the real-data local engine is not currently reachable."
        return state


def artistic_zebracns_state()->dict[str,Any]:
    """Return real-data state suitable for candidate scoring.

    If biological data is not loaded, callers receive an empty dictionary and
    therefore cannot accidentally treat the dormant UI backbone as a brain.
    """
    state=public_zebracns_state(max_age=0.12)
    if not state.get("ok") or not state.get("connected") or not state.get("biological_data_loaded"):
        return {}
    return state
