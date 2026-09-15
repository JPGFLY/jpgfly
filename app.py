"""JPGFLY autonomous fly drawing system and Backrooms-style archive."""
from __future__ import annotations

import asyncio, base64, functools, gzip, hashlib, json, logging, math, os, random, re, secrets, time, threading, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from candidate_brain import BRAIN_VERSION, BrainLimits, BrainRequest, configured_brain_mode, create_fly_brain
from brain_provider import ProceduralFlyBrain
from server_mechanics import ServerCanvasMechanics, FIGURE_MOTIFS
from flm_text_provider import configured_text_provider, generate_room_text, generate_room_fallback, generate_live_text
from studio_delta import install_studio_delta
from narrative_provider import narrative_mode, generate_live_comment, generate_room_record
from experience_memory import record_room_experience

ROOT=Path(__file__).resolve().parent; WEB=ROOT/"web"
SESSION_STATES=("CREATED","RUNNING","EVALUATING","FINALIZING","COMPLETED")
SESSIONS:dict[str,dict[str,Any]]={}
ARTWORKS:dict[str,dict[str,Any]]={}
ROOM_LOCK=threading.Lock(); FINALIZE_LOCK=threading.Lock(); NEXT_ROOM_NUMBER=1
CURRENT_STUDIO_ID:str|None=None
STUDIO_PROGRESS_AT=time.monotonic()
STUDIO_PROGRESS_WALL=datetime.now(timezone.utc).isoformat()
MAX_ACTIVE_SESSIONS=128; SESSION_TTL_SECONDS=21600; MAX_REQUEST_BYTES=8*1024*1024
BUILD_ID="BACKROOMS-THEME-DURATION-VARIATION-2026-09-13-41"
PUBLIC_LAUNCH_ID="20260913-0218"
TIME_STANDARD="UTC"
LOGGER=logging.getLogger("jpgfly")
CONTROL_METHODS={"POST","PUT","PATCH","DELETE"}
app=FastAPI(title="JPGFLY Backrooms",docs_url=None,redoc_url=None)


def _is_loopback(host:str) -> bool:
    return host in {"127.0.0.1","::1","localhost"}

@app.middleware("http")
async def harden_http(request:Request,call_next):
    length=request.headers.get("content-length")
    if length:
        try:
            if int(length)>MAX_REQUEST_BYTES:return Response("request too large",status_code=413)
        except ValueError:return Response("invalid content length",status_code=400)

    if request.method in CONTROL_METHODS:
        configured_token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip()
        client_host=request.client.host if request.client else ""
        if configured_token:
            supplied=request.headers.get("authorization","")
            expected="Bearer "+configured_token
            if not secrets.compare_digest(supplied,expected):
                return Response("control authorization required",status_code=403)
        elif not _is_loopback(client_host):
            return Response("remote control is disabled",status_code=403)

    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"]="same-origin"
    response.headers["Cross-Origin-Resource-Policy"]="same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"]="none"
    response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control","no-store")
    if os.environ.get("JPGFLY_HTTPS_ONLY","").lower()=="true":
        response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response

def synchronized(lock):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            with lock:return function(*args,**kwargs)
        return wrapped
    return decorate

PUBLIC_ACTIVITY=[
    {"timestamp":"03:14:07","category":"OBSERVATION","message":"Network activity detected"},
    {"timestamp":"03:14:12","category":"MEMORY","message":"Context boundary updated"},
    {"timestamp":"03:14:19","category":"BEHAVIOR","message":"Visual behavior shifted"},
    {"timestamp":"03:14:27","category":"ACTION","message":"Drawing session started"},
    {"timestamp":"03:15:03","category":"STATUS","message":"Autonomous fly brain active"},
]

class StartRequest(BaseModel):
    seed:int|None=None
    complexity:float=Field(default=.96,ge=.1,le=1)
    mutation:float=Field(default=.42,ge=0,le=1)
    density:float=Field(default=.64,ge=.1,le=1)
    limits:dict[str,int]|None=None

class DecisionRequest(BaseModel):
    sequence:int=Field(ge=0)
    observation:dict[str,Any]|None=None

class FinalizeRequest(BaseModel):
    client_fingerprint:str=Field(default="",max_length=128)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def mark_studio_progress():
    global STUDIO_PROGRESS_AT,STUDIO_PROGRESS_WALL
    STUDIO_PROGRESS_AT=time.monotonic();STUDIO_PROGRESS_WALL=datetime.now(timezone.utc).isoformat()
def digest(value):return "0x"+hashlib.sha256(canonical(value).encode()).hexdigest()
def public_session(session):return {k:v for k,v in session.items() if not k.startswith("_")}

def active_session_summary(session):
    """Public live-session metadata without the full private working state."""
    return {
        "session_id":session.get("session_id"),
        "status":session.get("status"),
        "brain_mode":session.get("brain_mode"),
        "brain_version":session.get("brain_version"),
        "decision_count":int(session.get("decision_count",0) or 0),
        "physical_action_count":int(session.get("physical_action_count",0) or 0),
        "duration":int(session.get("duration",0) or 0),
        "completion_reason":session.get("completion_reason"),
        "public_commentary":list(session.get("public_commentary") or [])[-12:],
    }

def data_root():
    configured=os.environ.get("JPGFLY_DATA_DIR","").strip() or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH","").strip()
    return Path(configured).expanduser().resolve() if configured else ROOT/".jpgfly"

def storage_root():return data_root()/"artworks"

def _env_true(name,default=False):
    raw=os.environ.get(name)
    if raw is None:return bool(default)
    return raw.strip().lower() in {"1","true","yes","on"}

def public_deployment_mode():
    return _env_true("JPGFLY_PUBLIC_DEPLOYMENT",False) or bool(os.environ.get("RAILWAY_ENVIRONMENT","").strip())

def validate_deployment_environment():
    """Fail closed on public deployments that would expose control or lose archives."""
    if not public_deployment_mode():
        return
    token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip()
    if len(token)<32:
        raise RuntimeError("Public JPGFLY deployment requires JPGFLY_CONTROL_TOKEN with at least 32 characters.")

    railway=bool(os.environ.get("RAILWAY_ENVIRONMENT","").strip())
    volume=os.environ.get("RAILWAY_VOLUME_MOUNT_PATH","").strip()
    if railway and not volume and not _env_true("JPGFLY_ALLOW_EPHEMERAL_STORAGE",False):
        raise RuntimeError("Railway deployment requires a persistent Volume. Attach one (recommended mount: /data) or explicitly set JPGFLY_ALLOW_EPHEMERAL_STORAGE=true.")

    root=data_root()
    root.mkdir(parents=True,exist_ok=True)
    if not os.access(root,os.W_OK):
        raise RuntimeError(f"JPGFLY data directory is not writable: {root}")
    try:
        root.relative_to(WEB.resolve())
        raise RuntimeError("JPGFLY_DATA_DIR must not be inside the public web directory.")
    except ValueError:
        pass

    provider=configured_text_provider()
    if provider in {"flm","hybrid"}:
        flm_url=os.environ.get("JPGFLY_FLM_URL","").strip()
        if not flm_url:
            raise RuntimeError(f"JPGFLY_TEXT_PROVIDER={provider} requires JPGFLY_FLM_URL in public deployment.")
        lowered=flm_url.casefold()
        if railway and any(host in lowered for host in ("127.0.0.1","localhost","[::1]")):
            raise RuntimeError("Railway cannot reach the local WSL FLM bridge at localhost. Configure a private/remote FLM service URL.")
        if not any(host in lowered for host in ("127.0.0.1","localhost","[::1]")):
            flm_token=os.environ.get("JPGFLY_FLM_AUTH_TOKEN","").strip()
            if len(flm_token)<32:
                raise RuntimeError("Remote FLM use requires JPGFLY_FLM_AUTH_TOKEN with at least 32 characters.")

    if provider in {"ollama","hybrid"}:
        ollama_url=os.environ.get("JPGFLY_OLLAMA_URL","").strip()
        if not ollama_url:
            raise RuntimeError(f"JPGFLY_TEXT_PROVIDER={provider} requires JPGFLY_OLLAMA_URL in public deployment.")
        lowered=ollama_url.casefold()
        if railway and any(host in lowered for host in ("127.0.0.1","localhost","[::1]")):
            raise RuntimeError("Railway cannot reach a local Ollama server at localhost. Configure a reachable private/remote Ollama URL.")
        if not any(host in lowered for host in ("127.0.0.1","localhost","[::1]")):
            ollama_token=os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
            if len(ollama_token)<32:
                raise RuntimeError("Remote Ollama use requires JPGFLY_OLLAMA_AUTH_TOKEN with at least 32 characters.")

def _compact_manifest(record,storage_meta):
    compact=json.loads(canonical(record))
    provenance=dict(compact.get("provenance") or {})
    provenance.pop("agentWallet",None)
    for key in ("completeFlyActionHistory","movementReplayEvents","evaluationCheckpoints"):
        provenance.pop(key,None)
    compact["provenance"]=provenance
    for key in ("brain_decisions","events","evaluation_checkpoints","artifact_uri","text_error"):
        compact.pop(key,None)
    compact["storage"]=storage_meta
    if provenance:
        hashes=dict(compact.get("hashes") or {})
        hashes["provenance"]=digest(provenance)
        hashes["completion"]=digest({"creationId":"0x"+compact["session_id"],"state":"COMPLETED","fingerprint":hashes.get("fingerprint"),"provenanceHash":hashes["provenance"]})
        compact["hashes"]=hashes
    return compact

def _archive_record_visible(record):
    return str(record.get("launch_id") or "") in {PUBLIC_LAUNCH_ID,"dumb-dumb"}

def load_artwork_record(session_id):
    if not re.fullmatch(r"[0-9a-f]{64}",session_id or ""):return None
    path=storage_root()/(session_id+".json")
    if not path.is_file():return None
    try:record=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return None
    provenance=record.get("provenance");hashes=record.get("hashes") or {}
    if provenance and hashes.get("provenance") and digest(provenance)!=hashes["provenance"]:return None
    if provenance and hashes.get("completion"):
        expected=digest({"creationId":"0x"+session_id,"state":"COMPLETED","fingerprint":hashes.get("fingerprint"),"provenanceHash":hashes.get("provenance")})
        if expected!=hashes["completion"]:return None
    if not _archive_record_visible(record):return None
    public_record=json.loads(canonical(record))
    public_provenance=dict(public_record.get("provenance") or {})
    if public_provenance.pop("agentWallet",None) is not None:
        public_record["provenance"]=public_provenance
        public_hashes=dict(public_record.get("hashes") or {})
        if public_provenance:
            public_hashes["provenance"]=digest(public_provenance)
            public_hashes["completion"]=digest({"creationId":"0x"+session_id,"state":"COMPLETED","fingerprint":public_hashes.get("fingerprint"),"provenanceHash":public_hashes["provenance"]})
        public_record["hashes"]=public_hashes
    return public_record

def load_artworks():
    global NEXT_ROOM_NUMBER
    directory=storage_root()
    if not directory.exists():return
    loaded=[]
    for path in directory.glob("*.json"):
        try:
            record=json.loads(path.read_text(encoding="utf-8"))
            if not _archive_record_visible(record):continue
            loaded.append(record)
        except (OSError,ValueError,KeyError):continue
    loaded.sort(key=lambda item:(item.get("completed_at") or "",item.get("session_id") or ""))
    used=set()
    for record in loaded:
        try:number=int(record.get("room_number") or 0)
        except (TypeError,ValueError):number=0
        if number>0:used.add(number)
    next_free=1
    for record in loaded:
        try:number=int(record.get("room_number") or 0)
        except (TypeError,ValueError):number=0
        if number<=0:
            while next_free in used:next_free+=1
            number=next_free;used.add(number);next_free+=1
            record["room_number"]=number
            record["room_code"]=f"ROOM-{number:04d}"
        ARTWORKS[record["session_id"]]=artwork_summary(record)
    NEXT_ROOM_NUMBER=(max(used)+1) if used else 1

def next_room_number():
    global NEXT_ROOM_NUMBER
    with ROOM_LOCK:
        number=NEXT_ROOM_NUMBER;NEXT_ROOM_NUMBER+=1;return number

def persist_artwork(record):
    directory=storage_root();directory.mkdir(parents=True,exist_ok=True);session_id=record["session_id"]
    frozen=json.loads(canonical(record));eligible=bool(frozen.get("launch_eligible"))
    frozen["launch_id"]=PUBLIC_LAUNCH_ID
    frozen["quality_tier"]="FULL_BRAIN" if eligible else "DUMB_DUMB"
    public_number=len(ARTWORKS)+1;frozen["room_number"]=public_number;frozen["room_code"]=f"ROOM-{public_number:04d}"
    prefix="data:image/svg+xml;base64,"
    uri=frozen.get("artifact_uri","")
    raw_svg=directory/(session_id+".svg")
    gz_svg=directory/(session_id+".svg.gz")

    if uri.startswith(prefix):
        svg_bytes=base64.b64decode(uri[len(prefix):])
    elif gz_svg.is_file():
        try:svg_bytes=gzip.decompress(gz_svg.read_bytes())
        except (OSError,gzip.BadGzipFile):raise RuntimeError("stored SVG is invalid")
    elif raw_svg.is_file():
        svg_bytes=raw_svg.read_bytes()
    else:
        raise RuntimeError("completed room has no SVG artifact")

    svg_gz=gzip.compress(svg_bytes,compresslevel=9,mtime=0)
    svg_name=session_id+".svg.gz"
    svg_tmp=directory/(svg_name+".tmp");svg_target=directory/svg_name
    svg_tmp.write_bytes(svg_gz);os.replace(svg_tmp,svg_target)

    storage_meta={
        "schema":4,
        "mode":"image+text",
        "artwork":svg_name,
        "artworkEncoding":"gzip",
        "artworkRawBytes":len(svg_bytes),
        "artworkCompressedBytes":len(svg_gz),
    }
    compact=_compact_manifest(frozen,storage_meta)
    temporary=directory/(session_id+".json.tmp");target=directory/(session_id+".json")
    temporary.write_text(json.dumps(compact,ensure_ascii=False,separators=(",",":")),encoding="utf-8");os.replace(temporary,target)

    for obsolete in (
        directory/(session_id+".replay.json.gz"),
        raw_svg,
    ):
        if obsolete.is_file():
            try:obsolete.unlink()
            except OSError:pass

    ARTWORKS[session_id]=artwork_summary(compact)

def archive_storage_stats():
    directory=storage_root()
    totals={"mode":"image+text","manifests":0,"artworks":0,"manifestBytes":0,"artworkBytes":0,"replays":0,"replayBytes":0,"videos":0,"videoBytes":0}
    if directory.exists():
        for path in directory.iterdir():
            if not path.is_file():continue
            size=path.stat().st_size
            name=path.name
            if name.endswith(".svg.gz") or name.endswith(".svg"):
                totals["artworks"]+=1;totals["artworkBytes"]+=size
            elif name.endswith(".json"):
                totals["manifests"]+=1;totals["manifestBytes"]+=size
            elif name.endswith(".replay.json.gz"):
                totals["replays"]+=1;totals["replayBytes"]+=size
            elif name.lower().endswith((".mp4",".webm",".mov")):
                totals["videos"]+=1;totals["videoBytes"]+=size
    totals["totalBytes"]=totals["manifestBytes"]+totals["artworkBytes"]+totals["replayBytes"]+totals["videoBytes"]
    return totals

def artwork_summary(record):
    summary={key:record.get(key) for key in ("session_id","room_number","room_code","room_title","room_description","memory_thread","anomaly_report","fly_statement","state","status","completed_at","concept","thought_fragments","public_commentary","brain_mode","brain_version","decision_count","duration","completion_reason","hashes","structural_metrics","visual_context","storage","launch_eligible","quality_tier")}
    summary["artifact_reference"]=(record.get("provenance") or {}).get("artifactReference") or record.get("artifact_reference")
    return summary|{"preview":f'/api/artworks/{record["session_id"]}/artwork.svg',"url":f'/artworks/{record["session_id"]}'}

def recent_room_memory(limit=6):
    ordered=sorted(ARTWORKS.values(),key=lambda item:item.get("completed_at","") or "",reverse=True)[:max(1,min(12,limit))]
    return [{
        "room_code":item.get("room_code"),
        "room_title":item.get("room_title"),
        "room_description":item.get("room_description"),
        "memory_thread":item.get("memory_thread"),
        "fly_statement":item.get("fly_statement"),
        "concept":item.get("concept"),
        "thought_fragments":(item.get("thought_fragments") or [])[-6:],
        "public_commentary":(item.get("public_commentary") or [])[-4:],
        "structural_metrics":item.get("structural_metrics"),
        "visual_context":item.get("visual_context"),
    } for item in ordered]

def live_narrative_context(session):
    records=session.get("brain_decisions") or []
    recent=[]
    for record in records[-12:]:
        action=record.get("action") or {}
        recent.append({
            "sequence":record.get("sequence"),
            "phase":action.get("phase"),
            "goal":action.get("autonomyGoal"),
            "movement":action.get("movementStyle"),
            "brush":action.get("brushTool"),
            "technique":action.get("technique"),
            "motif":action.get("motifHint"),
            "transform":action.get("motifTransform"),
            "relationship":action.get("relationshipToExistingMarks"),
            "reason":action.get("reason"),
            "color":action.get("color"),
            "scale":action.get("scale"),
            "composition_pass":action.get("compositionPass"),
            "region_target":action.get("regionTarget"),
            "macro_intent":action.get("macroIntent"),
        })
    observation=(records[-1].get("observation") or {}) if records else {}
    return {
        "session_id":session.get("session_id"),
        "status":session.get("status"),
        "decision_count":len(records),
        "recent_actions":recent,
        "canvas":{key:observation.get(key) for key in (
            "canvasOccupancy","negativeSpace","focalArea","nearbyLines","intersections",
            "densityBalance","repetition","meaningfulChangeRate","densityContrast",
            "localDensity","directionalUniformity","consecutiveLowChange"
        )},
        "recent_public_notes":(session.get("public_commentary") or [])[-16:],
        "earlier_rooms":recent_room_memory(8),
    }

def dumb_dumb_live_text(session,sequence):
    pool=(
        "line good.",
        "more pink.",
        "oops. keep going.",
        "this bit loud.",
        "tiny line. big mood.",
        "fly likes this.",
        "too much? no.",
        "circle-ish thing.",
        "black line won.",
        "cyan happened.",
        "wing brain says yes.",
        "mess is working.",
        "one more mark.",
        "scratch scratch.",
        "pretty accident.",
        "wrong. nice.",
        "keep the weird bit.",
        "fly forgot the plan.",
        "this corner hungry.",
        "okay. paint."
    )
    recent={str(item.get("text") or "") for item in (session.get("public_commentary") or [])[-18:] if isinstance(item,dict)}
    start=(int(session.get("seed",0))+int(sequence)*17)%len(pool)
    for offset in range(len(pool)):
        text=pool[(start+offset)%len(pool)]
        if text not in recent:
            return text
    return pool[start]

def dumb_dumb_room_text(context,seed):
    titles=("Oops Room","Fly Did A Thing","Lines Happened","No Plan Room","Pretty Accident","Brain Small, Paint Big")
    descriptions=(
        "Fly kept painting. Some lines behaved. Some did not.",
        "Color happened. Then more color happened. Fly approves.",
        "No big theory. Just marks, mess, and a room.",
        "Fly lost the plan and found this instead.",
        "A lot of lines showed up. They seem fine.",
        "Small brain day. Big paint day."
    )
    memories=(
        "Fly remembers the colors. Probably.",
        "Something here feels familiar. Not sure what.",
        "Keep this weird bit for later.",
        "Maybe next room steals one line.",
        "Memory fuzzy. Paint not fuzzy.",
        "Fly will remember enough."
    )
    anomalies=(
        "Too many lines. Still alive.",
        "One empty spot survived.",
        "Black line thinks it is boss.",
        "Pink got everywhere.",
        "Some shapes almost became things.",
        "Nothing exploded. Good."
    )
    statements=(
        "I kept going.",
        "I like the mess.",
        "No plan. Good.",
        "This one bit back.",
        "Paint first. Think later.",
        "Fly did fly stuff."
    )
    i=int(seed)%len(titles)
    return {
        "room_title":titles[i],
        "room_description":descriptions[i],
        "memory_thread":memories[i],
        "anomaly_report":anomalies[i],
        "fly_statement":statements[i],
    }

async def generate_studio_commentary(session_id,sequence):
    session=SESSIONS.get(session_id)
    provider=configured_text_provider()
    dumb_dumb=bool(session and "DUMB DUMB" in str(session.get("brain_mode") or ""))
    if not session or session.get("_commentary_busy") or (not dumb_dumb and provider not in ("ollama","flm","hybrid")):
        return
    session["_commentary_busy"]=True
    try:
        context=json.loads(canonical(live_narrative_context(session)))
        seed=int(session.get("seed",0))+int(sequence)*7919
        if dumb_dumb:
            comment=dumb_dumb_live_text(session,sequence)
        elif provider=="flm":
            comment=await asyncio.to_thread(generate_live_text,context,seed)
        elif provider=="hybrid":
            ollama_note=await asyncio.to_thread(generate_live_comment,context,seed)
            hybrid_context=dict(context)
            hybrid_context["ollama_note"]=ollama_note or ""
            try:
                comment=await asyncio.to_thread(generate_live_text,hybrid_context,seed+17)
            except Exception:
                comment=ollama_note
            if not comment:
                comment=ollama_note
        else:
            comment=await asyncio.to_thread(generate_live_comment,context,seed)
        session=SESSIONS.get(session_id)
        if not session or not comment:
            return
        entry={"sequence":int(sequence),"timestamp":int(session.get("duration",0) or 0),"text":comment,"provider":("DUMB_DUMB" if dumb_dumb else provider.upper())}
        session.setdefault("public_commentary",[]).append(entry)
        session["public_commentary"]=session["public_commentary"][-36:]
        session["events"].append({"type":"fly_comment","timestamp":entry["timestamp"],"sequence":entry["sequence"],"text":comment,"provider":entry["provider"]})
    except Exception as exc:
        session=SESSIONS.get(session_id)
        if session:
            session["_last_commentary_error"]=str(exc)[:240]
    finally:
        session=SESSIONS.get(session_id)
        if session:
            session["_commentary_busy"]=False

def derive_thought_fragments(records):
    """Turn recorded, observable action fields into short public-facing fragments."""
    candidates=[]
    def add(index,text,weight=1):
        if text and not any(item[1]==text for item in candidates):candidates.append((index,text,weight))
    for record_index,record in enumerate(records):
        action=record.get("action",{}); observation=record.get("observation",{})
        transform=action.get("motifTransform","none"); relation=action.get("relationshipToExistingMarks","")
        index=int(record.get("decision") or record.get("sequence") or record_index)
        if action.get("intent")=="FINISH_ARTWORK":add(index,"This is finished.",10);continue
        if not action.get("brushDown",True):continue
        reason=action.get("reason","")
        significance=4 if action.get("eraseIntent") else 3 if transform!="none" else 2 if action.get("evaluation") else 1
        add(index,reason,significance)
        if float(observation.get("densityContrast",0) or 0)>.48:add(index,"The uneven field is becoming useful.",2)
        if int(observation.get("intersections",0) or 0)>12 and relation not in ("avoid_overcrowding","selective_erase"):add(index,"The collisions are becoming the focal structure.",2)
    if not candidates:return []
    ordered=sorted(candidates,key=lambda item:item[0]);finish=[item for item in ordered if item[1]=="This is finished."]
    pool=[item for item in ordered if item[1]!="This is finished."]
    selected=[]
    if pool:
        slots=min(7,len(pool))
        for slot in range(slots):
            center=round(slot*(len(pool)-1)/max(1,slots-1));window=pool[max(0,center-2):min(len(pool),center+3)]
            pick=max(window,key=lambda item:(item[2],-abs(pool.index(item)-center)))
            if pick[1] not in selected:selected.append(pick[1])
        for item in sorted(pool,key=lambda item:(item[2],item[0]),reverse=True):
            if len(selected)>=7:break
            if item[1] not in selected:selected.append(item[1])
    if finish:selected.append("This is finished.")
    return selected[:8]

def derive_concept(records,metrics):
    actions=[record.get("action",{}) for record in records if record.get("action",{}).get("intent")=="MOVE"]
    if not actions:return "A completed JPGFLY composition."

    def ranked(field,default="gesture"):
        counts={}
        for action in actions:
            value=action.get(field)
            if value:counts[value]=counts.get(value,0)+1
        return sorted(counts,key=lambda value:(-counts[value],value)) or [default]

    styles=ranked("movementStyle")
    brushes=ranked("brushTool","ink_line")
    techniques=ranked("technique","continuous")
    dominant=styles[0]
    secondary=styles[1] if len(styles)>1 else None
    brush=brushes[0]
    technique=techniques[0]

    intersections=int(metrics.get("intersections",0) or 0)
    developments=int(metrics.get("motifDevelopments",0) or 0)
    erasures=int(metrics.get("erasureActions",0) or 0)
    branches=int(metrics.get("branchActions",0) or 0)

    movement=f"{dominant} motion"
    if secondary and secondary!=dominant:
        movement+=f" countered by {secondary}"

    structure=[]
    if intersections:
        structure.append(f"{intersections} recorded intersections")
    if developments:
        structure.append(f"{developments} motif transformations")
    if erasures:
        structure.append(f"{erasures} selective erasures")
    if branches:
        structure.append(f"{branches} branch actions")

    detail=", ".join(structure[:3]) if structure else "a restrained structural field"
    return f"Built from {movement}, using {brush} with {technique}; {detail} shaped the final composition."
def derive_room_profile(number,records,metrics,concept):
    actions=[r.get("action",{}) for r in records if r.get("action",{}).get("intent")=="MOVE"]
    motifs=[a.get("motifHint") for a in actions if a.get("motifHint") and a.get("motifHint")!="NONE"]
    modes=[a.get("compositionMode") for a in actions if a.get("compositionMode")]
    styles=[a.get("movementStyle") for a in actions if a.get("movementStyle")]
    tensions=[a.get("roomTension") for a in actions if a.get("roomTension")]
    dominant=max(set(motifs),key=motifs.count) if motifs else None
    dominant_style=max(set(styles),key=styles.count) if styles else "gesture"
    mode=max(set(modes),key=modes.count) if modes else "FIELD"
    tension=max(set(tensions),key=tensions.count) if tensions else ""
    intersections=int(metrics.get("intersections",0) or 0)

    title_words={"FLY":"Fly in the Wall","CAT_FACE":"The Cat Room","FISH":"Fish Signal","GHOST":"Occupied Air","SPIDER":"Web Room","MOTH":"Light Hunger","TV":"Dead Channel","EYEBALL":"The Watching Room","CLOCK":"Wrong Time","MASK":"Someone Else's Face"}
    style_titles={"scribble":"Static Weather","vortex":"False Center","wave":"Moving Quiet","ribbon":"Folded Signal","fracture":"Broken Agreement","lattice":"Bad Architecture","maze":"No Exit Yet","orbit":"Borrowed Gravity","coil":"Tight Memory","cross":"Interruption Field","contour":"Edge Without Owner","branch":"Nervous Network","spiral":"Returning Wrong","cluster":"Crowded Evidence","jitter":"Unstable Witness","sweep":"Long Gesture","web":"Shared Tension","petal":"Soft Repetition","starburst":"Impact Without Event"}
    if dominant:
        title=title_words.get(dominant,f"{dominant.replace('_',' ').title()} Field")
        anomaly_subject=dominant.replace('_',' ').lower()
    else:
        title=style_titles.get(dominant_style,f"{dominant_style.replace('_',' ').title()} Field")
        anomaly_subject=dominant_style.replace('_',' ').lower()

    room_code=f"ROOM-{number:04d}"
    tension_text=f" Its internal tension was {tension.replace('_',' ').lower()}." if tension else ""
    description=f"{room_code} formed as a {mode.replace('_',' ').lower()} composition dominated by {dominant_style.replace('_',' ')} movement.{tension_text} {concept}"
    anomaly=f"The fly kept returning to {anomaly_subject} behavior while producing {intersections} recorded intersections. The room was built through revision rather than from a predetermined finished image."
    final_reason=records[-1].get("action",{}).get("reason","It stopped when the field felt complete.") if records else "It stopped."
    statement=f"I kept changing the argument instead of naming the object. {final_reason}"
    return {"room_number":number,"room_code":room_code,"room_title":title,"room_description":description,"anomaly_report":anomaly,"fly_statement":statement}

def get_required(session_id):
    session=SESSIONS.get(session_id)
    if not session:raise HTTPException(404,"session not found")
    return session
def prune_sessions():
    now=time.monotonic()
    for session_id,session in list(SESSIONS.items()):
        if now-float(session.get("_created",now))>SESSION_TTL_SECONDS:SESSIONS.pop(session_id,None)

load_artworks()
NEXT_ROOM_NUMBER=max([int(item.get("room_number",item.get("collection_number",0)) or 0) for item in ARTWORKS.values()]+[0])+1

def parse_limits(raw):
    raw=raw or {}
    def bound(name,default,lo,hi):return max(lo,min(hi,int(raw.get(name,default))))
    return BrainLimits(bound("maxSessionDurationMs",600000,4000,900000),bound("maxBrainDecisions",800,8,900),bound("maxPhysicalActions",800,8,900),bound("maxConsecutiveLowChange",48,3,140))
def public_limits(l):return {"maxSessionDurationMs":l.max_session_duration_ms,"maxBrainDecisions":l.max_brain_decisions,"maxPhysicalActions":l.max_physical_actions,"maxConsecutiveLowChange":l.max_consecutive_low_change}

def expected_brush_profile(action):
    base=round(.8+float(action["pressure"])*6.4,2)
    profiles={"ink_line":(1,.92),"soft_paint":(2.15,.72),"dry_brush":(1.45,.76),"fine_pen":(.42,.98),"charcoal_grain":(1.35,.78),"wash":(3.1,.62),"stipple":(.78,.92),"splatter":(.7,.88),"subtractive":(1.7,1)}
    width_factor,opacity_base=profiles.get(action.get("brushTool"),profiles["ink_line"])
    return base,round(base*width_factor,2),round(opacity_base*(.9+float(action["pressure"])*.1),3)

def validate_mechanical_trace(session,events):
    """Validate that submitted physical events stay inside the brain action envelope."""
    records=session["brain_decisions"]
    brain_events=[event for event in events if event.get("type")=="brain_decision"]
    if len(brain_events)!=len(records):raise HTTPException(400,"movement stream does not match brain decisions")
    physical=[event for event in events if event.get("type") in ("stroke","move")]
    expected=[record for record in records if record["action"]["intent"]=="MOVE"]
    if len(physical)!=len(expected):raise HTTPException(400,"each brain movement must have exactly one physical action")
    by_decision={event.get("decision"):event for event in physical}
    if len(by_decision)!=len(physical):raise HTTPException(400,"duplicate physical action")
    position=[735.0,48.0]
    for sequence,record in enumerate(records):
        action=record["action"]; brain=brain_events[sequence]
        if brain.get("decision")!=sequence or brain.get("intent")!=action["intent"]:raise HTTPException(400,"brain event mismatch")
        if action["intent"]!="MOVE":continue
        event=by_decision.get(sequence); expected_type="stroke" if action["brushDown"] else "move"
        if not event or event.get("type")!=expected_type:raise HTTPException(400,"physical action contradicts fly decision")
        expected_duration=round(max(90,min(1500,action["duration"]+action["hesitation"])))
        if int(event.get("duration",-1))!=expected_duration:raise HTTPException(400,"physical timing contradicts fly decision")
        if expected_type=="stroke":
            points=event.get("points")
            if not isinstance(points,list) or not 2<=len(points)<=96:raise HTTPException(400,"invalid incremental stroke")
            if any(not isinstance(p,list) or len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(float(v)) for v in p) for p in points):raise HTTPException(400,"invalid stroke coordinates")
            if any(not (24<=float(p[0])<=776 and 24<=float(p[1])<=476) for p in points):raise HTTPException(400,"stroke leaves the mechanical canvas")
            if math.dist(points[0],position)>.01:raise HTTPException(400,"foreleg trace is discontinuous")
            length=sum(math.dist(points[i-1],points[i]) for i in range(1,len(points)))
            figure_multiplier=1.87 if action.get("motifHint") in FIGURE_MOTIFS else 1.02
            if length>float(action["movementDistance"])*figure_multiplier+.2:raise HTTPException(400,"stroke exceeds fly movement")
            if event.get("color")!=action["color"] or bool(event.get("erase",False))!=action["eraseIntent"]:raise HTTPException(400,"brush execution contradicts fly decision")
            if event.get("brushTool")!=action.get("brushTool") or event.get("technique")!=action.get("technique"):raise HTTPException(400,"tool execution contradicts fly decision")
            expected_base,expected_width,expected_opacity=expected_brush_profile(action)
            try:base_width=float(event.get("baseWidth",-1));width=float(event.get("width",-1));opacity=float(event.get("opacity",-1))
            except (TypeError,ValueError):raise HTTPException(400,"invalid brush metrics")
            if not all(math.isfinite(v) for v in (base_width,width,opacity)):raise HTTPException(400,"invalid brush metrics")
            if abs(base_width-expected_base)>.02 or abs(width-expected_width)>.02 or abs(opacity-expected_opacity)>.002:raise HTTPException(400,"brush execution mismatch")
            position=[float(points[-1][0]),float(points[-1][1])]
        else:
            start=event.get("from"); end=event.get("to")
            if not isinstance(start,list) or not isinstance(end,list) or len(start)!=2 or len(end)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(float(v)) for v in start+end):raise HTTPException(400,"invalid foreleg move")
            if not (24<=float(end[0])<=776 and 24<=float(end[1])<=476) or math.dist(start,position)>.01 or math.dist(start,end)>float(action["movementDistance"])+.05:raise HTTPException(400,"foreleg move contradicts fly decision")
            position=[float(end[0]),float(end[1])]

def artwork_svg(events):
    marks=[]
    for event in events:
        if event.get("type")!="stroke":continue
        raw=event["points"];points=" ".join(f'{float(p[0]):.3f},{float(p[1]):.3f}' for p in raw)
        tool=event.get("brushTool","ink_line");technique=event.get("technique","continuous");correction=bool(event.get("erase")) or tool=="subtractive"
        color="#ffffff" if correction else event["color"];width=float(event["width"]);opacity=1 if correction else float(event.get("opacity",1))
        poly=lambda w=width,o=opacity,dx=0,dy=0:f'<polyline points="{points}" transform="translate({dx:.2f} {dy:.2f})" fill="none" stroke="{color}" stroke-width="{w:.2f}" stroke-opacity="{o:.3f}" stroke-linecap="round" stroke-linejoin="round"/>'
        if tool in ("stipple","splatter") or technique=="stippling":
            dots=[];count=4 if tool=="splatter" else 1;seed=int(event.get("decision",0))+1
            for i,p in enumerate(raw[::2]):
                for dot in range(count):
                    spread=width*(2.7 if tool=="splatter" else .45);angle=math.sin((seed*37+i*38+dot*53)*.91)*math.tau;radius=spread*((.25+((i*2+dot)%5)/5) if tool=="splatter" else .25);size=max(.55,width*(.11 if tool=="splatter" else .22)*(1+dot*.18))
                    dots.append(f'<circle cx="{float(p[0])+math.cos(angle)*radius:.3f}" cy="{float(p[1])+math.sin(angle)*radius:.3f}" r="{size:.3f}" fill="{color}" fill-opacity="{opacity:.3f}"/>')
            marks.extend(dots)
        elif technique in ("hatching","cross_hatching"):
            for i in range(1,len(raw),2):
                a,p=raw[i-1],raw[i];angle=math.atan2(p[1]-a[1],p[0]-a[0])+math.pi/2;length=5+width*1.8
                for flip in ((1,-1) if technique=="cross_hatching" else (1,)):
                    x1=p[0]-math.cos(angle+.55*flip)*length;y1=p[1]-math.sin(angle+.55*flip)*length;x2=p[0]+math.cos(angle+.55*flip)*length;y2=p[1]+math.sin(angle+.55*flip)*length
                    marks.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{color}" stroke-width="{max(.55,width*.28):.2f}" stroke-opacity="{opacity:.3f}" stroke-linecap="round"/>')
        elif tool in ("wash","soft_paint") or technique=="layered_glazing":marks.extend((poly(width*1.35,max(.58,opacity*.78)),poly(width*.62,max(.70,opacity*.94))))
        elif tool in ("dry_brush","charcoal_grain") or technique=="smudged_dragging":marks.extend((poly(width*.24,max(.56,opacity*.72),-width*.34,-width*.22),poly(width*.54,opacity),poly(width*.24,max(.56,opacity*.72),width*.34,width*.22)))
        elif technique=="overpainting":marks.extend((poly(width*1.45,max(.58,opacity*.72)),poly(width*.56,max(.72,opacity*.94))))
        else:marks.append(poly())
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500"><rect width="800" height="500" fill="#ffffff"/>'+''.join(marks)+'</svg>'
    return svg,"data:image/svg+xml;base64,"+base64.b64encode(svg.encode()).decode()

@app.get("/")
def index():return FileResponse(WEB/"index.html",headers={"Cache-Control":"no-store"})
@app.get("/live")
def live():return FileResponse(WEB/"live.html",headers={"Cache-Control":"no-store"})
@app.get("/archive")
def archive():return FileResponse(WEB/"archive.html",headers={"Cache-Control":"no-store"})
@app.get("/artworks/{session_id}")
def artwork_page(session_id:str):return FileResponse(WEB/"artwork.html",headers={"Cache-Control":"no-store"})
@app.get("/images/fly.png")
def fly_image():return FileResponse(WEB/"images"/"fly.png",media_type="image/png",headers={"Cache-Control":"no-store"})
@app.get("/images/fly.webp")
def fly_image_compat():return FileResponse(WEB/"images"/"fly.png",media_type="image/png",headers={"Cache-Control":"no-store"})
@app.get("/images/fly-agent.webp")
def fly_agent_image_compat():return FileResponse(WEB/"images"/"fly.png",media_type="image/png",headers={"Cache-Control":"no-store"})
@app.get("/assets/{name}")
def asset(name:str):
    if Path(name).name!=name or Path(name).suffix not in {".js",".mjs",".css"}:raise HTTPException(404)
    path=WEB/name
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,headers={"Cache-Control":"no-cache, must-revalidate"})

@app.get("/api/config")
def public_config():
    return {"project":"JPGFLY","agentWallet":os.environ.get("JPGFLY_AGENT_WALLET","0x977d02F5519be02Cc3B8905e1D39f916DC4A3e9D").strip() or "0x977d02F5519be02Cc3B8905e1D39f916DC4A3e9D","build":BUILD_ID,"mode":"BACKROOMS","archiveMode":"image+text","replayStorage":False,"videoStorage":False,"timeStandard":TIME_STANDARD,"brainMode":configured_brain_mode(),"textProvider":configured_text_provider().upper(),"modelStack":"QWEN + FLM","artBrain":"FLY BRAIN","visualEngine":"FLY BRAIN","flyLanguageModel":"FLM","autonomousStudio":os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()!="false","currentStudioSession":CURRENT_STUDIO_ID}

@app.get("/api/public/activity")
def public_activity():return {"mode":"LIVE","events":PUBLIC_ACTIVITY}

@app.get("/api/studio/malecns")
def public_malecns_state():
    enabled=os.environ.get("JPGFLY_MALECNS_ENABLED","").strip().lower() in {"1","true","yes","on"} or bool(os.environ.get("JPGFLY_MALECNS_URL","").strip())
    if not enabled:
        return {"ok":False,"enabled":False,"dataset":"MaleCNS v1.0","top_active":[]}
    configured=os.environ.get("JPGFLY_MALECNS_URL","").strip().rstrip("/")
    ollama=os.environ.get("JPGFLY_OLLAMA_URL","").strip().rstrip("/")
    url=configured or (ollama[:-7]+"/malecns" if ollama.endswith("/ollama") else "http://127.0.0.1:4690")
    headers={}
    token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
    if token:headers["authorization"]="Bearer "+token
    try:
        request=urllib.request.Request(url+"/state",headers=headers)
        with urllib.request.urlopen(request,timeout=4) as response:
            state=json.load(response)
        bias=state.get("bias") if isinstance(state.get("bias"),dict) else {}
        top=[]
        for item in (state.get("top_active") or [])[:96]:
            if not isinstance(item,dict):continue
            clean={
                "body_id":str(item.get("body_id") or ""),
                "index":int(item.get("index",0) or 0),
                "spikes":int(item.get("spikes",0) or 0),
            }
            for key in ("u","v"):
                try:
                    value=float(item.get(key))
                    if math.isfinite(value):clean[key]=value
                except (TypeError,ValueError):
                    pass
            if item.get("superclass") is not None:
                clean["superclass"]=str(item.get("superclass"))[:80]
            top.append(clean)
        return {
            "ok":True,
            "enabled":True,
            "dataset":"MaleCNS v1.0",
            "neurons":int(state.get("neurons",166700) or 166700),
            "directed_edges":int(state.get("directed_edges",25582938) or 25582938),
            "bias":bias,
            "top_active":top,
            "spatial_activity":any("u" in item and "v" in item for item in top),
        }
    except Exception as exc:
        LOGGER.warning("MaleCNS public telemetry unavailable: %s: %s",type(exc).__name__,str(exc)[:180])
        return {"ok":False,"enabled":True,"dataset":"MaleCNS v1.0","top_active":[]}


@app.get("/api/studio/malecns/network")
def public_malecns_network():
    enabled=os.environ.get("JPGFLY_MALECNS_ENABLED","").strip().lower() in {"1","true","yes","on"} or bool(os.environ.get("JPGFLY_MALECNS_URL","").strip())
    if not enabled:
        return {"ok":False,"enabled":False,"dataset":"MaleCNS v1.0","nodes":[],"edges":[]}
    configured=os.environ.get("JPGFLY_MALECNS_URL","").strip().rstrip("/")
    ollama=os.environ.get("JPGFLY_OLLAMA_URL","").strip().rstrip("/")
    url=configured or (ollama[:-7]+"/malecns" if ollama.endswith("/ollama") else "http://127.0.0.1:4690")
    headers={}
    token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
    if token:headers["authorization"]="Bearer "+token
    try:
        request=urllib.request.Request(url+"/network",headers=headers)
        with urllib.request.urlopen(request,timeout=5) as response:
            state=json.load(response)
        nodes=[]
        for item in (state.get("nodes") or [])[:420]:
            if not isinstance(item,dict):continue
            nodes.append({
                "body_id":str(item.get("body_id") or ""),
                "spikes":int(item.get("spikes",0) or 0),
                "active":bool(item.get("active")),
                "superclass":str(item.get("superclass") or "")[:80],
            })
        valid={item["body_id"] for item in nodes if item["body_id"]}
        edges=[]
        for item in (state.get("edges") or [])[:2400]:
            if not isinstance(item,dict):continue
            source=str(item.get("source") or "");target=str(item.get("target") or "")
            if source not in valid or target not in valid:continue
            try:weight=float(item.get("weight",0) or 0)
            except (TypeError,ValueError):weight=0.0
            edges.append({"source":source,"target":target,"weight":weight})
        return {
            "ok":True,
            "enabled":True,
            "dataset":"MaleCNS v1.0",
            "neurons":int(state.get("neurons",166700) or 166700),
            "directed_edges":int(state.get("directed_edges",25582938) or 25582938),
            "telemetry_schema":str(state.get("telemetry_schema") or ""),
            "nodes":nodes,
            "edges":edges,
            "important_note":"Live node/edge identities and spike counts are real MaleCNS simulation telemetry. Layout is topology-derived, not anatomical coordinates.",
        }
    except Exception as exc:
        LOGGER.warning("MaleCNS public network unavailable: %s: %s",type(exc).__name__,str(exc)[:180])
        return {"ok":False,"enabled":True,"dataset":"MaleCNS v1.0","nodes":[],"edges":[]}


@app.get("/api/version")
def version():return {"build":BUILD_ID,"mode":"BACKROOMS","autonomousStudio":os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()!="false"}

@app.get("/api/health")
def health():
    enabled=os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()!="false"
    session=SESSIONS.get(CURRENT_STUDIO_ID) if CURRENT_STUDIO_ID else None
    return {"ok":True,"project":"JPGFLY","build":BUILD_ID,"studio":{"enabled":enabled,"state":session.get("status") if session else "BETWEEN_ROOMS","decisionCount":session.get("decision_count",0) if session else 0,"lastProgressAt":STUDIO_PROGRESS_WALL,"secondsSinceProgress":round(max(0.0,time.monotonic()-STUDIO_PROGRESS_AT),1)},"textProvider":configured_text_provider().upper(),"archiveMode":"image+text","persistentVolume":bool(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH","").strip()) if os.environ.get("RAILWAY_ENVIRONMENT") else None,"rooms":len(ARTWORKS)}

@app.get("/api/studio/current")
def studio_current():
    if not CURRENT_STUDIO_ID:raise HTTPException(404,"studio is between rooms")
    session=SESSIONS.get(CURRENT_STUDIO_ID)
    if session:return active_session_summary(session)
    record=load_artwork_record(CURRENT_STUDIO_ID)
    if record:return record
    raise HTTPException(404,"studio session unavailable")

@app.get("/api/studio/status")
def studio_status():
    session=SESSIONS.get(CURRENT_STUDIO_ID) if CURRENT_STUDIO_ID else None
    return {"enabled":os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()!="false","session_id":CURRENT_STUDIO_ID,"state":session.get("status") if session else "BETWEEN_ROOMS","decision_count":session.get("decision_count",0) if session else 0,"rooms":len(ARTWORKS)}

install_studio_delta(app, lambda: CURRENT_STUDIO_ID, SESSIONS, load_artwork_record, canonical, configured_text_provider)

@app.post("/api/sessions")
async def create_session(request:StartRequest):
    prune_sessions()
    if len(SESSIONS)>=MAX_ACTIVE_SESSIONS:raise HTTPException(503,"too many active creation sessions")
    session_id=secrets.token_hex(32); seed=(request.seed if request.seed is not None else int(session_id[:8],16))&0xffffffff
    limits=parse_limits(request.limits); brain=create_fly_brain(seed,complexity=request.complexity,mutation=request.mutation,density=request.density); mechanics=ServerCanvasMechanics(seed,session_id)
    dumb_brain=ProceduralFlyBrain(seed,request.complexity,request.mutation,request.density,getattr(brain,"experience",{}) or {})
    dumb_brain.mode="DUMB DUMB MODE · PURE PYTHON FALLBACK"
    session={"session_id":session_id,"status":"CREATED","seed":seed,"brain_mode":brain.mode,"brain_version":BRAIN_VERSION,"parameters":{"complexity":request.complexity,"mutation":request.mutation,"density":request.density},"limits":public_limits(limits),"decision_count":0,"physical_action_count":0,"brain_decisions":[],"evaluation_checkpoints":[],"public_commentary":[],"completion_reason":None,"events":mechanics.events,"hashes":{},"_brain":brain,"_dumb_brain":dumb_brain,"_mechanics":mechanics,"_limits":limits,"_decision_lock":asyncio.Lock(),"_commentary_busy":False,"_full_brain_from_start":None,"_created":time.monotonic(),"_accepting":True,"_frozen":False}
    SESSIONS[session_id]=session; return public_session(session)

@app.get("/api/sessions")
def compare_sessions():
    return {"sessions":[artwork_summary(record) for record in sorted(ARTWORKS.values(),key=lambda item:item.get("completed_at","") or "",reverse=True)[:12]]}

@app.get("/api/artworks/recent")
def recent_artworks(limit:int=9):
    selected=sorted(ARTWORKS.values(),key=lambda item:item.get("completed_at","") or "",reverse=True)[:max(1,min(12,limit))]
    return {"artworks":[artwork_summary(record) for record in selected]}

def artwork_search_blob(record):
    parts=[
        record.get("room_code"),record.get("room_title"),record.get("room_description"),record.get("memory_thread"),
        record.get("anomaly_report"),record.get("fly_statement"),record.get("concept"),
        record.get("brain_mode"),record.get("brain_version"),record.get("completion_reason"),
    ]
    parts.extend(record.get("thought_fragments") or [])
    for entry in record.get("public_commentary") or []:
        if isinstance(entry,dict):parts.append(entry.get("text"))
        elif entry:parts.append(entry)
    metrics=record.get("structural_metrics")
    if metrics:parts.append(canonical(metrics))
    visual_context=record.get("visual_context")
    if visual_context:parts.append(canonical(visual_context))
    return " ".join(str(part) for part in parts if part).casefold()

@app.get("/api/storage")
def storage_stats():
    return archive_storage_stats()

@app.get("/api/artworks")
def archive_artworks(offset:int=0,limit:int=24,q:str=""):
    ordered=sorted(ARTWORKS.values(),key=lambda item:item.get("completed_at","") or "",reverse=True)
    terms=[term for term in re.split(r"\s+",(q or "").strip().casefold()) if term]
    if terms:
        ordered=[record for record in ordered if all(term in artwork_search_blob(record) for term in terms)]
    start=max(0,offset);count=max(1,min(60,limit));selected=ordered[start:start+count]
    return {"artworks":[artwork_summary(record) for record in selected],"offset":start,"limit":count,"total":len(ordered),"hasMore":start+len(selected)<len(ordered),"query":q}

@app.get("/api/artworks/{session_id}")
def get_artwork(session_id:str):
    if session_id not in ARTWORKS:raise HTTPException(404,"artwork not found")
    record=load_artwork_record(session_id)
    if not record:raise HTTPException(404,"artwork record unavailable")
    return record

@app.get("/api/artworks/{session_id}/artwork.svg")
def get_artwork_svg(session_id:str):
    if session_id not in ARTWORKS:raise HTTPException(404,"artwork not found")
    manifest=load_artwork_record(session_id) or {}
    storage=manifest.get("storage") or {}
    gz_name=storage.get("artwork")
    if gz_name and str(gz_name).endswith(".svg.gz"):
        path=storage_root()/gz_name
        if not path.is_file():raise HTTPException(404,"artwork image not found")
        try:
            raw=gzip.decompress(path.read_bytes())
        except (OSError,gzip.BadGzipFile):
            raise HTTPException(500,"artwork integrity check failed")
        expected=(manifest.get("provenance") or {}).get("artifactReference") or (ARTWORKS.get(session_id) or {}).get("artifact_reference")
        actual="jpgfly-svg:"+hashlib.sha256(raw).hexdigest()
        if expected and actual!=expected:raise HTTPException(500,"artwork integrity check failed")
        return FileResponse(path,media_type="image/svg+xml",headers={"Content-Encoding":"gzip","Cache-Control":"public, max-age=31536000, immutable"})

    path=storage_root()/(session_id+".svg")
    record=ARTWORKS.get(session_id) or {}
    if path.is_file():
        try:svg_bytes=path.read_bytes()
        except OSError:raise HTTPException(503,"artwork image unavailable")
        expected=record.get("artifact_reference")
        actual="jpgfly-svg:"+hashlib.sha256(svg_bytes).hexdigest()
        if expected and actual!=expected:raise HTTPException(500,"artwork integrity check failed")
        return Response(svg_bytes,media_type="image/svg+xml",headers={"Cache-Control":"public, max-age=31536000, immutable"})

    full=load_artwork_record(session_id) or {}
    prefix="data:image/svg+xml;base64,";uri=full.get("artifact_uri","")
    if not uri.startswith(prefix):raise HTTPException(404,"artwork image not found")
    svg_bytes=base64.b64decode(uri[len(prefix):]);expected=(full.get("provenance") or {}).get("artifactReference")
    if expected and "jpgfly-svg:"+hashlib.sha256(svg_bytes).hexdigest()!=expected:raise HTTPException(500,"artwork integrity check failed")
    return Response(svg_bytes,media_type="image/svg+xml",headers={"Cache-Control":"public, max-age=31536000, immutable"})

@app.get("/api/sessions/{session_id}")
def get_session(session_id):
    session=SESSIONS.get(session_id)
    if session:return active_session_summary(session)
    record=load_artwork_record(session_id)
    if not record:raise HTTPException(404,"session not found")
    return record

@app.post("/api/sessions/{session_id}/decision")
async def session_decision(session_id:str,request:DecisionRequest):
    session=get_required(session_id)
    async with session["_decision_lock"]:
        if session["status"] not in ("CREATED","RUNNING") or not session["_accepting"]:raise HTTPException(409,"session is not accepting drawing actions")
        decisions=session["brain_decisions"]
        if request.sequence<len(decisions):
            record=decisions[request.sequence]
            return {"action":record["action"],"observation":record["observation"],"events":[],"serverClock":session["_mechanics"].clock,"state":session["status"],"brainMode":session["brain_mode"],"sequence":request.sequence,"replayed":True}
        if request.sequence!=len(decisions):raise HTTPException(409,"decision sequence mismatch")
        mechanics=session["_mechanics"];observation=mechanics.observe(len(decisions));before=len(session["events"])
        try:
            action=await asyncio.to_thread(session["_brain"].decide,BrainRequest(observation=observation),session["_limits"])
        except Exception:
            LOGGER.exception("Fly Brain decision failed; switching session to DUMB DUMB pure-Python fallback")
            session["_brain"]=session["_dumb_brain"]
            session["_brain"].mode="DUMB DUMB MODE · PURE PYTHON FALLBACK"
            action=await asyncio.to_thread(session["_brain"].decide,BrainRequest(observation=observation),session["_limits"])
        data=action.model_dump()
        session["brain_mode"]=session["_brain"].mode
        fly_brain_ok="DUMB DUMB" not in str(session["brain_mode"]).upper()
        if session.get("_full_brain_from_start") is None:session["_full_brain_from_start"]=fly_brain_ok
        elif not fly_brain_ok:session["_full_brain_from_start"]=False
        session["launch_eligible"]=session.get("_full_brain_from_start") is True
        record={"sequence":request.sequence,"observation":observation,"observationHash":digest(observation),"action":data};decisions.append(record);session["decision_count"]=len(decisions)
        session["events"].append({"type":"brain_decision","timestamp":mechanics.clock,"decision":request.sequence,"intent":data["intent"],"phase":data["phase"],"movementStyle":data["movementStyle"],"brushTool":data["brushTool"],"technique":data["technique"],"brushDown":data["brushDown"],"decisionMode":data.get("decisionMode"),"motifMode":data.get("motifMode"),"suggestedForm":data.get("suggestedForm"),"candidateCount":data.get("candidateCount",0),"contextPass":data.get("contextPass"),"memoryContext":data.get("memoryContext") or []})
        if data.get("evaluation"):
            session["evaluation_checkpoints"].append(data["evaluation"]);session["events"].append({"type":"evaluate","timestamp":mechanics.clock,**data["evaluation"]})
        if data["intent"]=="FINISH_ARTWORK":
            mechanics.lift();session.update(status="EVALUATING",completion_reason=data["reason"],_accepting=False)
            session["events"].append({"type":"state_change","timestamp":mechanics.clock,"state":"EVALUATING"});session["events"].append({"type":"finish_artwork","timestamp":mechanics.clock,"reason":data["reason"]})
        else:
            mechanics.execute(data,request.sequence);session["status"]="RUNNING"
        session["physical_action_count"]=mechanics.physicalActionCount;session["duration"]=mechanics.clock
        if data["intent"]!="FINISH_ARTWORK" and configured_text_provider() in ("ollama","flm","hybrid") and (len(decisions)%8==0 or bool(data.get("evaluation"))):
            asyncio.create_task(generate_studio_commentary(session_id,request.sequence))
        return {"action":data,"observation":observation,"events":json.loads(canonical(session["events"][before:])),"serverClock":mechanics.clock,"state":session["status"],"brainMode":session["brain_mode"],"sequence":request.sequence,"replayed":False}

@app.post("/api/sessions/{session_id}/finalize")
@synchronized(FINALIZE_LOCK)
def finalize_session(session_id:str,request:FinalizeRequest):
    session=get_required(session_id)
    if session["_frozen"]:return public_session(session)
    if session["status"]!="EVALUATING" or not session["brain_decisions"] or session["brain_decisions"][-1]["action"]["intent"]!="FINISH_ARTWORK":raise HTTPException(409,"the fly has not finished this artwork")
    events=json.loads(canonical(session["events"]))
    if not events or any(not isinstance(event,dict) or "type" not in event for event in events):raise HTTPException(500,"invalid authoritative movement event stream")
    finish_indexes=[i for i,e in enumerate(events) if e.get("type")=="finish_artwork"]
    if len(finish_indexes)!=1 or any(e.get("type") in ("stroke","move","tip_down") for e in events[finish_indexes[0]+1:]):raise HTTPException(400,"drawing events exist after finish")
    validate_mechanical_trace(session,events)
    session["status"]="FINALIZING"
    final_timestamp=max(int(e.get("timestamp",0)) for e in events)+180
    events.append({"type":"state_change","timestamp":final_timestamp-180,"state":"FINALIZING"}); events.append({"type":"session_end","sessionId":session_id,"timestamp":final_timestamp}); events.append({"type":"state_change","timestamp":final_timestamp,"state":"COMPLETED"})
    actions=[record["action"] for record in session["brain_decisions"] if record["action"]["intent"]=="MOVE"]
    scales=[float(action.get("scale",1)) for action in actions]
    structural_metrics={"markFamilies":sorted({action["movementStyle"] for action in actions}),"familyCounts":{style:sum(1 for action in actions if action["movementStyle"]==style) for style in sorted({action["movementStyle"] for action in actions})},"brushTools":sorted({action.get("brushTool","ink_line") for action in actions}),"brushCounts":{tool:sum(1 for action in actions if action.get("brushTool")==tool) for tool in sorted({action.get("brushTool","ink_line") for action in actions})},"techniques":sorted({action.get("technique","continuous") for action in actions}),"techniqueCounts":{technique:sum(1 for action in actions if action.get("technique")==technique) for technique in sorted({action.get("technique","continuous") for action in actions})},"phaseCounts":{phase:sum(1 for action in actions if action["phase"]==phase) for phase in ("EXPLORATION","STRUCTURE","DEVELOPMENT","CONTRAST","REFINEMENT","RESOLUTION")},"layerCounts":{layer:sum(1 for action in actions if action.get("layerRole")==layer) for layer in ("PRIMARY","SECONDARY","TERTIARY")},"motifDevelopments":sum(1 for action in actions if action.get("motifTransform","none")!="none"),"branchActions":sum(1 for action in actions if action["movementStyle"]=="branch"),"erasureActions":sum(1 for action in actions if action["eraseIntent"]),"scaleRange":[round(min(scales),3),round(max(scales),3)] if scales else [0,0],"compositionPassCounts":{value:sum(1 for action in actions if action.get("compositionPass")==value) for value in sorted({action.get("compositionPass") for action in actions if action.get("compositionPass")})},"macroIntentCounts":{value:sum(1 for action in actions if action.get("macroIntent")==value) for value in sorted({action.get("macroIntent") for action in actions if action.get("macroIntent")})},"regionTargets":{str(value):sum(1 for action in actions if action.get("regionTarget")==value) for value in sorted({action.get("regionTarget") for action in actions if isinstance(action.get("regionTarget"),int) and action.get("regionTarget")>=0})},"intersections":int(session["brain_decisions"][-1]["observation"].get("intersections",0))}
    structural_metrics["decisionModeCounts"]={value:sum(1 for action in actions if action.get("decisionMode")==value) for value in sorted({action.get("decisionMode") for action in actions if action.get("decisionMode")})}
    structural_metrics["contextPassCounts"]={value:sum(1 for action in actions if action.get("contextPass")==value) for value in sorted({action.get("contextPass") for action in actions if action.get("contextPass")})}
    structural_metrics["roomTensionCounts"]={value:sum(1 for action in actions if action.get("roomTension")==value) for value in sorted({action.get("roomTension") for action in actions if action.get("roomTension")})}
    visual_context=session["_brain"].context_snapshot() if hasattr(session["_brain"],"context_snapshot") else {}
    svg,artifact_uri=artwork_svg(events); artifact="jpgfly-svg:"+hashlib.sha256(svg.encode()).hexdigest()
    room_number=next_room_number();completed_at=datetime.now(timezone.utc).isoformat()
    thoughts=derive_thought_fragments(session["brain_decisions"]);concept=derive_concept(session["brain_decisions"],structural_metrics);room=derive_room_profile(room_number,session["brain_decisions"],structural_metrics,concept)
    text_provider="PROCEDURAL"
    actions=[record.get("action",{}) for record in session["brain_decisions"] if record.get("action",{}).get("intent")=="MOVE"]
    stride=max(1,len(actions)//24)
    timeline=[]
    for index in range(0,len(actions),stride):
        action=actions[index]
        timeline.append({
            "decision":index,
            "phase":action.get("phase"),
            "goal":action.get("autonomyGoal"),
            "composition_mode":action.get("compositionMode"),
            "subgoal":action.get("subgoal"),
            "movement":action.get("movementStyle"),
            "brush":action.get("brushTool"),
            "technique":action.get("technique"),
            "motif":action.get("motifHint"),
            "transform":action.get("motifTransform"),
            "relationship":action.get("relationshipToExistingMarks"),
            "scene_relation":action.get("sceneRelation"),
            "reason":action.get("reason"),
            "color":action.get("color"),
            "scale":action.get("scale"),
            "context_pass":action.get("contextPass"),
            "room_tension":action.get("roomTension"),
        })
    context={
        "room_code":room["room_code"],
        "concept":concept,
        "completion_reason":session["completion_reason"],
        "decision_count":len(session["brain_decisions"]),
        "duration_ms":final_timestamp,
        "thought_fragments":thoughts,
        "public_commentary":(session.get("public_commentary") or [])[-18:],
        "structural_metrics":structural_metrics,
        "timeline":timeline[:28],
        "motif_counts":{value:sum(1 for action in actions if action.get("motifHint")==value) for value in sorted({action.get("motifHint") for action in actions if action.get("motifHint") and action.get("motifHint")!="NONE"})},
        "composition_mode_counts":{value:sum(1 for action in actions if action.get("compositionMode")==value) for value in sorted({action.get("compositionMode") for action in actions if action.get("compositionMode")})},
        "goal_counts":{value:sum(1 for action in actions if action.get("autonomyGoal")==value) for value in sorted({action.get("autonomyGoal") for action in actions if action.get("autonomyGoal")})},
        "decision_mode_counts":{value:sum(1 for action in actions if action.get("decisionMode")==value) for value in sorted({action.get("decisionMode") for action in actions if action.get("decisionMode")})},
        "motif_mode_counts":{value:sum(1 for action in actions if action.get("motifMode")==value) for value in sorted({action.get("motifMode") for action in actions if action.get("motifMode")})},
        "room_tension_counts":{value:sum(1 for action in actions if action.get("roomTension")==value) for value in sorted({action.get("roomTension") for action in actions if action.get("roomTension")})},
        "context_pass_counts":{value:sum(1 for action in actions if action.get("contextPass")==value) for value in sorted({action.get("contextPass") for action in actions if action.get("contextPass")})},
        "visual_context":visual_context,
        "color_counts":{value:sum(1 for action in actions if action.get("color")==value) for value in sorted({action.get("color") for action in actions if action.get("color")})},
        "earlier_rooms":recent_room_memory(8),
    }
    try:
        if "DUMB DUMB" in str(session.get("brain_mode") or ""):
            room.update(dumb_dumb_room_text(context,session["seed"]))
            text_provider="DUMB_DUMB"
        elif configured_text_provider()=="hybrid":
            ollama_draft=None
            try:
                ollama_draft=generate_room_record(context,session["seed"])
            except Exception:
                LOGGER.exception("Hybrid Ollama director failed; FLM will continue alone")
            hybrid_context=dict(context)
            hybrid_context["ollama_draft"]=ollama_draft or {}
            try:
                generated=generate_room_text(hybrid_context,session["seed"]+101)
            except Exception:
                if ollama_draft:
                    generated=ollama_draft
                    text_provider="OLLAMA"
                else:
                    raise
            if generated:
                room.update(generated)
                if text_provider!="OLLAMA":
                    text_provider="OLLAMA+FLM"
        elif narrative_mode()=="ollama":
            generated=generate_room_record(context,session["seed"])
            if generated:
                room.update(generated);text_provider="OLLAMA"
        elif configured_text_provider()=="flm":
            generated=generate_room_text(context,session["seed"])
            if generated:
                room.update(generated);text_provider="FLM"
        else:
            # Never publish the old mechanical caption-like profile. Even with no
            # external language model configured, the public room gets the richer
            # memory-aware literary fallback.
            room.update(generate_room_fallback(context,session["seed"]))
            text_provider="LITERARY_FALLBACK"
    except Exception as exc:
        LOGGER.exception("Room text generation failed")
        if "DUMB DUMB" in str(session.get("brain_mode") or ""):
            room.update(dumb_dumb_room_text(context,session["seed"]))
            text_provider="DUMB_DUMB"
        else:
            room.update(generate_room_fallback(context,session["seed"]))
            text_provider="LITERARY_FALLBACK"
        session["_room_text_error"]=str(exc)[:500]

    # Third-party/optional writers may not yet implement the memory-thread field.
    # Fill only that missing field without overwriting successful generated prose.
    if not room.get("memory_thread"):
        if "DUMB DUMB" in str(session.get("brain_mode") or ""):
            room["memory_thread"]=dumb_dumb_room_text(context,session["seed"]).get("memory_thread","")
        else:
            room["memory_thread"]=generate_room_fallback(context,session["seed"]).get("memory_thread","")
    decision_history_hash=digest(session["brain_decisions"])
    event_history_hash=digest(events)
    evaluation_history_hash=digest(session["evaluation_checkpoints"])
    fingerprint=digest({"seed":session["seed"],"decisionHistoryHash":decision_history_hash,"eventHistoryHash":event_history_hash,"evaluationHistoryHash":evaluation_history_hash})
    provenance={"archive":"JPGFLY Backrooms","creationId":"0x"+session_id,"artifactReference":artifact,"timeStandard":TIME_STANDARD,"decisionHistoryHash":decision_history_hash,"eventHistoryHash":event_history_hash,"evaluationHistoryHash":evaluation_history_hash,"visualContextHash":digest(visual_context)}
    provenance_hash=digest(provenance); completion_hash=digest({"creationId":"0x"+session_id,"state":"COMPLETED","fingerprint":fingerprint,"provenanceHash":provenance_hash})
    session.update(status="COMPLETED",state="COMPLETED",**room,completed_at=completed_at,concept=concept,thought_fragments=thoughts,text_provider=text_provider,text_error=session.get("_room_text_error"),events=events,provenance=provenance,artifact_uri=artifact_uri,duration=final_timestamp,structural_metrics=structural_metrics,visual_context=visual_context,hashes={"fingerprint":fingerprint,"provenance":provenance_hash,"completion":completion_hash},_frozen=True)
    # Learn from the authoritative completed room before compact persistence drops
    # the heavy decision/event history. This keeps future rooms autobiographical
    # without storing replay payloads.
    try:
        record_room_experience(public_session(session))
    except Exception:
        LOGGER.exception("Could not update JPGFLY visual experience")
    persist_artwork(public_session(session))
    result=load_artwork_record(session_id) or artwork_summary(session)
    SESSIONS.pop(session_id,None)
    return result

async def autonomous_studio_loop():
    global CURRENT_STUDIO_ID
    speed=max(.02,float(os.environ.get("JPGFLY_STUDIO_TIME_SCALE","0.25")))
    between=max(.2,float(os.environ.get("JPGFLY_STUDIO_BETWEEN_ROOMS","2.0")))
    while True:
        try:
            studio_seed=secrets.randbits(32)
            studio_rng=random.Random(studio_seed^0xA5A5A5A5)
            started=await create_session(StartRequest(
                seed=studio_seed,
                complexity=round(studio_rng.uniform(.72,.99),3),
                mutation=round(studio_rng.uniform(.34,.78),3),
                density=round(studio_rng.uniform(.42,.84),3),
                limits={"maxSessionDurationMs":900000,"maxBrainDecisions":900,"maxPhysicalActions":900,"maxConsecutiveLowChange":96},
            ))
            CURRENT_STUDIO_ID=started["session_id"];mark_studio_progress()
            while True:
                session=SESSIONS.get(CURRENT_STUDIO_ID)
                if not session or session["status"] not in ("CREATED","RUNNING"):break
                before=int(session.get("duration",0) or 0)
                await session_decision(CURRENT_STUDIO_ID,DecisionRequest(sequence=len(session["brain_decisions"])))
                mark_studio_progress()
                session=SESSIONS.get(CURRENT_STUDIO_ID)
                if not session:break
                after=int(session.get("duration",before) or before)
                await asyncio.sleep(max(.14,min(4.0,(after-before)/1000*speed)))
            session=SESSIONS.get(CURRENT_STUDIO_ID)
            if session and session["status"]=="EVALUATING":
                await asyncio.to_thread(finalize_session,CURRENT_STUDIO_ID,FinalizeRequest(client_fingerprint="autonomous-studio"));mark_studio_progress()
            await asyncio.sleep(between)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Autonomous studio loop failed")
            await asyncio.sleep(3)

async def studio_watchdog_loop():
    while True:
        await asyncio.sleep(15)
        if os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()=="false":
            continue
        task=getattr(app.state,"studio_task",None)
        if task is None or task.done():
            if task is not None:
                try:
                    error=task.exception()
                except (asyncio.CancelledError,Exception):
                    error=None
                if error:
                    LOGGER.error("Autonomous studio task stopped: %r",error)
            LOGGER.warning("Restarting autonomous studio task")
            app.state.studio_task=asyncio.create_task(autonomous_studio_loop())
            mark_studio_progress()

@app.on_event("startup")
async def start_autonomous_studio():
    validate_deployment_environment()
    if os.environ.get("JPGFLY_AUTONOMOUS_STUDIO","true").lower()=="false":return
    mark_studio_progress()
    app.state.studio_task=asyncio.create_task(autonomous_studio_loop())
    app.state.studio_watchdog_task=asyncio.create_task(studio_watchdog_loop())

@app.on_event("shutdown")
async def stop_autonomous_studio():
    for name in ("studio_task","studio_watchdog_task"):
        task=getattr(app.state,name,None)
        if task and not task.done():
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass

if __name__=="__main__":
    import uvicorn; uvicorn.run(app,host="127.0.0.1",port=4673)
