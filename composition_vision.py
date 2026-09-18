"""Vision-guided composition teacher for JPGFLY.

This module never generates artwork. It rasterizes the authoritative stroke
history, asks a local vision-language model to critique composition, and returns
small structured guidance that the Fly brain can use for later physical strokes.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

LOGGER=logging.getLogger("jpgfly.composition_vision")

CANVAS_W=800
CANVAS_H=500
PREVIEW_W=480
PREVIEW_H=300
_FAIL_LOCK=threading.Lock()
_FAIL_COUNT=0
_OPEN_UNTIL=0.0


class VisionComposition(BaseModel):
    composition_score: float=Field(ge=0,le=1)
    focal_strength: float=Field(ge=0,le=1)
    balance: float=Field(ge=0,le=1)
    relation_coherence: float=Field(ge=0,le=1)
    subject_readability: float=Field(ge=0,le=1)
    negative_space_quality: float=Field(ge=0,le=1)
    depth: float=Field(ge=0,le=1)
    next_goal: str
    target_x: float=Field(ge=0,le=1)
    target_y: float=Field(ge=0,le=1)
    secondary_x: float=Field(default=.5,ge=0,le=1)
    secondary_y: float=Field(default=.5,ge=0,le=1)
    structure: str="ASYMMETRIC"
    flow: str=""
    avoid: str=""
    note: str=""

    def compact(self)->dict[str,Any]:
        return {
            "score":round(self.composition_score,3),
            "focal":round(self.focal_strength,3),
            "balance":round(self.balance,3),
            "relations":round(self.relation_coherence,3),
            "readability":round(self.subject_readability,3),
            "negativeSpace":round(self.negative_space_quality,3),
            "depth":round(self.depth,3),
            "nextGoal":str(self.next_goal)[:48],
            "target":[round(self.target_x,3),round(self.target_y,3)],
            "secondaryTarget":[round(self.secondary_x,3),round(self.secondary_y,3)],
            "structure":str(self.structure)[:32],
            "flow":str(self.flow)[:96],
            "avoid":str(self.avoid)[:96],
            "note":str(self.note)[:160],
        }


_UNIT_FIELDS=(
    "composition_score","focal_strength","balance","relation_coherence",
    "subject_readability","negative_space_quality","depth","target_x","target_y",
    "secondary_x","secondary_y",
)


def _normalize_unit_value(value:Any)->Any:
    """Accept the model's occasional 0-10/0-100 scale without losing a critique."""
    try:
        number=float(value)
    except (TypeError,ValueError):
        return value
    if not (number==number) or number in (float("inf"),float("-inf")):
        return value
    if 0.0<=number<=1.0:
        return number
    if 1.0<number<=10.0:
        return number/10.0
    if 10.0<number<=100.0:
        return number/100.0
    return max(0.0,min(1.0,number))


def _normalize_vision_payload(value:Any)->Any:
    if not isinstance(value,dict):
        return value
    normalized=dict(value)
    for key in _UNIT_FIELDS:
        if key in normalized:
            normalized[key]=_normalize_unit_value(normalized[key])
    return normalized


def _safe_point(value):
    try:
        return float(value[0]),float(value[1])
    except (TypeError,ValueError,IndexError):
        return None


def render_canvas_preview(paths:list[list[list[float]]], *, current_position=None)->str:
    """Return a compact base64 PNG from authoritative canvas paths."""
    image=Image.new("RGB",(PREVIEW_W,PREVIEW_H),"white")
    draw=ImageDraw.Draw(image)
    sx=PREVIEW_W/CANVAS_W
    sy=PREVIEW_H/CANVAS_H

    total=max(1,len(paths))
    for index,path in enumerate(paths[-650:]):
        if not isinstance(path,list) or len(path)<2:
            continue
        points=[]
        for raw in path:
            point=_safe_point(raw)
            if point:
                points.append((round(point[0]*sx,2),round(point[1]*sy,2)))
        if len(points)<2:
            continue
        age=(index+max(0,total-650))/total
        shade=int(92-(age*64))
        width=1 if age<.72 else 2
        draw.line(points,fill=(shade,shade,shade),width=width,joint="curve")

    tip=_safe_point(current_position)
    if tip:
        x=tip[0]*sx;y=tip[1]*sy
        draw.ellipse((x-3,y-3,x+3,y+3),outline=(160,160,160),width=1)

    buffer=io.BytesIO()
    image.save(buffer,format="PNG",optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ollama_url()->str:
    base=os.environ.get("JPGFLY_OLLAMA_URL","http://127.0.0.1:11434").strip().rstrip("/")
    return base+"/api/chat"


def _headers()->dict[str,str]:
    headers={"content-type":"application/json"}
    token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
    if token:
        headers["authorization"]="Bearer "+token
    return headers


def _circuit_open()->bool:
    with _FAIL_LOCK:
        return time.monotonic()<_OPEN_UNTIL


def _record_success()->None:
    global _FAIL_COUNT,_OPEN_UNTIL
    with _FAIL_LOCK:
        _FAIL_COUNT=0
        _OPEN_UNTIL=0.0


def _record_failure()->None:
    global _FAIL_COUNT,_OPEN_UNTIL
    with _FAIL_LOCK:
        _FAIL_COUNT+=1
        if _FAIL_COUNT>=2:
            cooldown=max(30,min(300,int(os.environ.get("JPGFLY_VISION_COOLDOWN","90") or 90)))
            _OPEN_UNTIL=time.monotonic()+cooldown


def analyze_composition(paths:list[list[list[float]]], context:dict[str,Any]|None=None)->dict[str,Any]:
    """Ask the local vision model how the existing drawing should develop.

    Fail-open by design. Repeated remote/model failures trip a short circuit
    breaker so visual analysis can never stall the physical drawing loop.
    """
    if os.environ.get("JPGFLY_VISION_COMPOSITION","true").lower()=="false":
        return {}
    if _circuit_open():
        return {}

    model=os.environ.get("JPGFLY_VISION_MODEL","qwen3-vl:8b-instruct-q4_K_M").strip() or "qwen3-vl:8b-instruct-q4_K_M"
    timeout=max(6,min(45,int(os.environ.get("JPGFLY_VISION_TIMEOUT","18") or 18)))
    context=dict(context or {})
    image_b64=render_canvas_preview(paths,current_position=context.get("current_position"))

    initial=bool(context.get("initial"))
    prompt=(
        "You are JPGFLY's visual composition teacher. "
        +("The canvas is blank or nearly blank. Establish a composition BEFORE drawing: choose a strong primary focal region and a secondary counterweight. Do not list a bag of subjects. " if initial else "Study the CURRENT DRAWING only. ")
        +"You do not create an image and you do not prescribe exact paths. Diagnose whether "
        "the marks read as one intentional image rather than unrelated motifs. Judge focal "
        "hierarchy, balance, negative space, depth, subject readability, and especially whether "
        "subjects visually relate to each other. Choose next_goal from exactly: "
        "CONNECT_SUBJECTS, STRENGTHEN_FOCAL, CLARIFY_SUBJECT, BUILD_DEPTH, OPEN_NEGATIVE_SPACE, "
        "DEVELOP_COUNTERWEIGHT, SIMPLIFY, RESOLVE. target_x and target_y are the normalized PRIMARY "
        "region for drawing effort; secondary_x and secondary_y are a counterweight or relational "
        "anchor. All numeric scores and coordinates must be decimals from 0.0 to 1.0. structure must be one of "
        "ASYMMETRIC, DIAGONAL, TRIANGLE, CENTRAL, TWO_MASS, VERTICAL, HORIZONTAL. flow briefly describes how "
        "the eye should move between those regions. Do not ask to add a new unrelated object merely for variety. "
        "Prefer developing and connecting what already exists. Keep flow, avoid and note extremely short. Session context: "
        +json.dumps({
            "subject_program":context.get("subject_program"),
            "composition_mode":context.get("composition_mode"),
            "phase":context.get("phase"),
            "recent_motifs":context.get("recent_motifs",[])[:6],
            "art_style":context.get("art_style"),
        },separators=(",",":"))
    )

    payload={
        "model":model,
        "stream":False,
        "think":False,
        "format":VisionComposition.model_json_schema(),
        "messages":[{
            "role":"user",
            "content":prompt,
            "images":[image_b64],
        }],
        "keep_alive":os.environ.get("JPGFLY_VISION_KEEP_ALIVE","5m").strip() or "5m",
        "options":{"temperature":0.10,"num_predict":220,"num_ctx":4096},
    }
    request=urllib.request.Request(
        _ollama_url(),
        data=json.dumps(payload,separators=(",",":")).encode(),
        method="POST",
        headers=_headers(),
    )
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            result=json.load(response)
        raw=((result.get("message") or {}).get("content") or "").strip()
        parsed_payload=_normalize_vision_payload(json.loads(raw))
        parsed=VisionComposition.model_validate(parsed_payload)
        _record_success()
        return parsed.compact()
    except urllib.error.HTTPError as exc:
        _record_failure()
        LOGGER.warning("Vision composition HTTP failure status=%s",exc.code)
    except Exception as exc:
        _record_failure()
        LOGGER.warning("Vision composition unavailable: %s: %s",type(exc).__name__,str(exc)[:180])
    return {}
