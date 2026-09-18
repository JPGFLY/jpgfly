"""JPGFLY Brain 7.1 learned visual policy.

Bounded temporal art-policy network used as one vote inside the candidate
painter. Architecture: 96 -> 128 -> 64 -> 5.
"""
from __future__ import annotations
import json, math, os, threading
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:
    np=None

SCHEMA=2
INPUT_SIZE=96
H1=128
H2=64
OUTPUT_SIZE=5
MODE_ORDER=("ABSTRACT_BUILD","CONNECT","REVISIT","CONTRADICT","NEGATIVE_SPACE","ERASE","FINISH")
PASS_ORDER=("GROUND","ECHO","COUNTER","INTEGRATE","EDIT_RESOLVE")
TEMPERAMENT_ORDER=("OBSESSIVE","VIOLENT_MINIMAL","TENDER","ARCHITECTURAL","NERVOUS","MONUMENTAL","ASCETIC","DECAYING")
_LOCK=threading.RLock()
_POLICY=None

def _clamp(v,lo=0.0,hi=1.0):
    try:v=float(v)
    except (TypeError,ValueError):v=0.0
    return max(lo,min(hi,v))

def _signed(v,limit=1.0):
    try:v=float(v)
    except (TypeError,ValueError):v=0.0
    return max(-limit,min(limit,v))

def _root():
    configured=os.environ.get("JPGFLY_DATA_DIR","").strip() or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH","").strip()
    return Path(configured).expanduser().resolve() if configured else (Path(__file__).resolve().parent/".jpgfly")

def policy_path():
    configured=os.environ.get("JPGFLY_ART_POLICY_PATH","").strip()
    return Path(configured).expanduser().resolve() if configured else _root()/"art-policy-v2.json"

def legacy_policy_path():
    return _root()/"art-policy-v1.json"

def _sig(signals,name):
    return _clamp((signals or {}).get(name,0))

def _grid12(observation):
    raw=observation.get("regionDensityGrid12") or observation.get("regionDensity") or []
    if not isinstance(raw,list):raw=[]
    values=[_clamp(v) for v in raw[:12]]
    return values+[0.0]*(12-len(values))

def _history_block(history):
    recent=list(history or [])[-8:]
    if not recent:return [0.0]*32
    mode_counts={name:0 for name in MODE_ORDER}
    erase_count=revisit_count=0
    avg_scale=avg_pressure=avg_distance=avg_curvature=focus_reuse=0.0
    for record in recent:
        action=record.get("action") or {}
        mode=str(action.get("decisionMode") or "")
        if mode in mode_counts:mode_counts[mode]+=1
        erase_count+=int(bool(action.get("eraseIntent")))
        revisit_count+=int(mode=="REVISIT")
        avg_scale+=float(action.get("scale",1) or 1)
        avg_pressure+=float(action.get("pressure",0) or 0)
        avg_distance+=float(action.get("movementDistance",0) or 0)
        avg_curvature+=abs(float(action.get("curvature",0) or 0))
        relation=str(action.get("relationshipToExistingMarks") or "").casefold()
        focus_reuse+=float(any(word in relation for word in ("return","revisit","reinforce","repeat","connect")))
    n=float(len(recent))
    values=[min(1.0,mode_counts[name]/4.0) for name in MODE_ORDER]
    values.extend([min(1.0,erase_count/n),min(1.0,revisit_count/n),_clamp(avg_scale/n/2.5),_clamp(avg_pressure/n),_clamp(avg_distance/n/220.0),_clamp(avg_curvature/n/3.2),_clamp(focus_reuse/n)])
    first_obs=recent[0].get("observation") or {}
    last_obs=recent[-1].get("observation") or {}
    for key in ("canvasOccupancy","localDensity","repetition","directionalUniformity","densityContrast","regionalContrast","meaningfulChangeRate","intersections"):
        before=float(first_obs.get(key,0) or 0);after=float(last_obs.get(key,0) or 0)
        scale=24.0 if key=="intersections" else 1.0
        values.append(_signed((after-before)/scale))
    pass_counts={name:0 for name in PASS_ORDER}
    for record in recent:
        name=str((record.get("action") or {}).get("contextPass") or "")
        if name in pass_counts:pass_counts[name]+=1
    values.extend(min(1.0,pass_counts[name]/3.0) for name in PASS_ORDER)
    last_action=recent[-1].get("action") or {}
    values.extend([1.0 if last_action.get("brushDown") else 0.0,1.0 if last_action.get("eraseIntent") else 0.0,_clamp(float(last_action.get("scale",1) or 1)/2.5),_clamp(last_action.get("pressure",0)),_clamp(float(last_action.get("movementDistance",0) or 0)/220.0)])
    if len(values)!=32:raise RuntimeError(f"history feature size mismatch: {len(values)}")
    return values

def features(observation:dict[str,Any],action:dict[str,Any],mode=None,context_pass=None,zebra=None,history=None,room_context=None):
    observation=observation or {};action=action or {};room_context=room_context or {}
    mode=str(mode or action.get("decisionMode") or "ABSTRACT_BUILD")
    context_pass=str(context_pass or action.get("contextPass") or "GROUND")
    zebra=zebra or action.get("zebracnsActivity") or {}
    signals=zebra.get("signals") if isinstance(zebra.get("signals"),dict) else {}
    values=[
        _clamp(observation.get("canvasOccupancy",0)),_clamp(observation.get("localDensity",0)),_clamp(observation.get("repetition",0)),_clamp(observation.get("directionalUniformity",0)),
        _clamp(observation.get("densityContrast",0)),_clamp(observation.get("regionalContrast",0)),_clamp(observation.get("meaningfulChangeRate",0)),_clamp(float(observation.get("consecutiveLowChange",0) or 0)/20.0),
        _clamp(float(observation.get("occupiedRegions",0) or 0)/12.0),math.tanh(max(0.0,float(observation.get("intersections",0) or 0))/24.0),
        _clamp(observation.get("focusStrength",0)),_clamp(observation.get("emptySpaceBalance",0)),_clamp(observation.get("hierarchyStrength",0)),_clamp(observation.get("edgePressure",0)),
        _clamp(observation.get("focalCommitment",0)),_clamp(observation.get("overworkRisk",0)),_clamp(observation.get("revisionPotential",0)),
    ]
    values.extend(_grid12(observation))
    values.extend([1.0 if action.get("brushDown") else 0.0,1.0 if action.get("eraseIntent") else 0.0,_clamp(float(action.get("movementDistance",0) or 0)/220.0),_clamp(action.get("pressure",0)),_clamp(abs(float(action.get("curvature",0) or 0))/3.2),_clamp(float(action.get("scale",1) or 1)/2.5),_clamp(float(action.get("branchingDepth",0) or 0)/6.0)])
    values.extend(1.0 if mode==name else 0.0 for name in MODE_ORDER)
    values.extend(1.0 if context_pass==name else 0.0 for name in PASS_ORDER)
    temperament=str(room_context.get("artistic_temperament") or action.get("artisticTemperament") or "")
    values.extend(1.0 if temperament==name else 0.0 for name in TEMPERAMENT_ORDER)
    values.extend([_sig(signals,"novelty_seek"),_sig(signals,"attention_lock"),_sig(signals,"persistence"),_sig(signals,"state_instability"),_sig(signals,"repetition_drive"),_sig(signals,"completion_pressure"),_sig(signals,"arousal"),_sig(signals,"escape_drive")])
    values.extend(_history_block(history))
    if len(values)!=INPUT_SIZE:raise RuntimeError(f"art policy feature size mismatch: got {len(values)}, expected {INPUT_SIZE}")
    return values

def _legacy_features(observation,action,mode,context_pass,zebra):
    signals=(zebra or {}).get("signals") if isinstance((zebra or {}).get("signals"),dict) else {}
    values=[_clamp(observation.get("canvasOccupancy",0)),_clamp(observation.get("localDensity",0)),_clamp(observation.get("repetition",0)),_clamp(observation.get("directionalUniformity",0)),_clamp(observation.get("densityContrast",0)),_clamp(observation.get("regionalContrast",0)),_clamp(observation.get("meaningfulChangeRate",0)),_clamp(float(observation.get("consecutiveLowChange",0) or 0)/20.0),_clamp(float(observation.get("occupiedRegions",0) or 0)/12.0),math.tanh(max(0.0,float(observation.get("intersections",0) or 0))/24.0),1.0 if action.get("brushDown") else 0.0,1.0 if action.get("eraseIntent") else 0.0,_clamp(float(action.get("movementDistance",0) or 0)/220.0),_clamp(action.get("pressure",0)),_clamp(abs(float(action.get("curvature",0) or 0))/3.2),_clamp(float(action.get("scale",1) or 1)/2.5),_clamp(float(action.get("branchingDepth",0) or 0)/6.0)]
    values.extend(1.0 if mode==name else 0.0 for name in MODE_ORDER)
    values.extend(1.0 if context_pass==name else 0.0 for name in PASS_ORDER)
    values.extend([_sig(signals,"novelty_seek"),_sig(signals,"attention_lock"),_sig(signals,"persistence"),_sig(signals,"state_instability"),_sig(signals,"repetition_drive"),_sig(signals,"completion_pressure")])
    return values

class LegacyTeacher:
    def __init__(self):
        self.available=False
        if np is None:return
        path=legacy_policy_path()
        if not path.is_file():return
        try:
            data=json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema")!=1:return
            self.w1=np.asarray(data["w1"],dtype=np.float32);self.b1=np.asarray(data["b1"],dtype=np.float32);self.w2=np.asarray(data["w2"],dtype=np.float32);self.b2=float(data.get("b2",0) or 0)
            self.available=self.w1.shape==(14,35) and self.b1.shape==(14,) and self.w2.shape==(14,)
        except Exception:self.available=False
    def predict(self,x):
        if not self.available:return 0.0
        vector=np.asarray(x,dtype=np.float32)
        hidden=np.tanh(self.w1@vector+self.b1)
        return float(np.tanh(np.dot(self.w2,hidden)+self.b2))

class ArtPolicy:
    def __init__(self,path=None):
        self.path=path or policy_path();self.available=np is not None;self.rooms_trained=0;self.samples_trained=0;self.mean_reward=0.0;self.legacy_teacher=LegacyTeacher()
        if not self.available:return
        rng=np.random.default_rng(0x4A504746)
        self.w1=rng.uniform(-.055,.055,(H1,INPUT_SIZE)).astype(np.float32);self.b1=np.zeros(H1,dtype=np.float32)
        self.w2=rng.uniform(-.055,.055,(H2,H1)).astype(np.float32);self.b2=np.zeros(H2,dtype=np.float32)
        self.w3=rng.uniform(-.055,.055,(OUTPUT_SIZE,H2)).astype(np.float32);self.b3=np.zeros(OUTPUT_SIZE,dtype=np.float32)
        self._load()
    def _load(self):
        if not self.available or not self.path.is_file():return
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema")!=SCHEMA:return
            w1=np.asarray(data["w1"],dtype=np.float32);b1=np.asarray(data["b1"],dtype=np.float32);w2=np.asarray(data["w2"],dtype=np.float32);b2=np.asarray(data["b2"],dtype=np.float32);w3=np.asarray(data["w3"],dtype=np.float32);b3=np.asarray(data["b3"],dtype=np.float32)
            if w1.shape!=(H1,INPUT_SIZE) or b1.shape!=(H1,) or w2.shape!=(H2,H1) or b2.shape!=(H2,) or w3.shape!=(OUTPUT_SIZE,H2) or b3.shape!=(OUTPUT_SIZE,):return
            self.w1,self.b1,self.w2,self.b2,self.w3,self.b3=w1,b1,w2,b2,w3,b3
            self.rooms_trained=max(0,int(data.get("rooms_trained",0) or 0));self.samples_trained=max(0,int(data.get("samples_trained",0) or 0));self.mean_reward=float(data.get("mean_reward",0) or 0)
        except Exception:return
    def save(self):
        if not self.available:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={"schema":SCHEMA,"input_size":INPUT_SIZE,"h1":H1,"h2":H2,"output_size":OUTPUT_SIZE,"rooms_trained":self.rooms_trained,"samples_trained":self.samples_trained,"mean_reward":round(self.mean_reward,6),"w1":self.w1.tolist(),"b1":self.b1.tolist(),"w2":self.w2.tolist(),"b2":self.b2.tolist(),"w3":self.w3.tolist(),"b3":self.b3.tolist()}
        tmp=self.path.with_suffix(self.path.suffix+".tmp");tmp.write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8");os.replace(tmp,self.path)
    def _forward(self,matrix):
        h1=np.tanh(matrix@self.w1.T+self.b1);h2=np.tanh(h1@self.w2.T+self.b2);out=np.tanh(h2@self.w3.T+self.b3);return h1,h2,out
    def predict(self,x):
        if not self.available:return {"value":0.0,"tension":0.0,"restraint":0.0,"edit_bias":0.0,"focus_commitment":0.0}
        with _LOCK:
            _,_,out=self._forward(np.asarray(x,dtype=np.float32).reshape(1,-1));v=out[0]
            return {"value":float(v[0]),"tension":float(v[1]),"restraint":float(v[2]),"edit_bias":float(v[3]),"focus_commitment":float(v[4])}
    def vote(self,x):
        predicted=self.predict(x);confidence=min(1.0,self.rooms_trained/60.0,self.samples_trained/6000.0)
        return {**predicted,"value_vote":predicted["value"]*.65*confidence,"confidence":confidence}
    def train(self,samples,epochs=4,learning_rate=.008,batch_size=64):
        if not self.available:raise RuntimeError("Brain 7.1 training requires NumPy")
        samples=list(samples)
        if not samples:return
        x=np.asarray([item[0] for item in samples],dtype=np.float32);y=np.asarray([item[1] for item in samples],dtype=np.float32)
        rng=np.random.default_rng(0x7131+self.rooms_trained+self.samples_trained)
        with _LOCK:
            for _ in range(max(1,int(epochs))):
                order=rng.permutation(len(x))
                for start in range(0,len(x),max(8,int(batch_size))):
                    ids=order[start:start+max(8,int(batch_size))];xb,yb=x[ids],y[ids];h1,h2,out=self._forward(xb);batch=max(1,len(ids))
                    d3=(2.0/batch)*(out-yb)*(1.0-out*out);old_w3=self.w3.copy();old_w2=self.w2.copy()
                    grad_w3=d3.T@h2+.00008*self.w3;grad_b3=d3.sum(axis=0)
                    d2=(d3@old_w3)*(1.0-h2*h2);grad_w2=d2.T@h1+.00005*self.w2;grad_b2=d2.sum(axis=0)
                    d1=(d2@old_w2)*(1.0-h1*h1);grad_w1=d1.T@xb+.00005*self.w1;grad_b1=d1.sum(axis=0)
                    self.w3-=learning_rate*grad_w3;self.b3-=learning_rate*grad_b3;self.w2-=learning_rate*grad_w2;self.b2-=learning_rate*grad_b2;self.w1-=learning_rate*grad_w1;self.b1-=learning_rate*grad_b1
                self.w1=np.clip(self.w1,-1.5,1.5);self.w2=np.clip(self.w2,-1.5,1.5);self.w3=np.clip(self.w3,-1.5,1.5)
            self.samples_trained+=len(samples)*max(1,int(epochs))
    def status(self):
        confidence=min(1.0,self.rooms_trained/60.0,self.samples_trained/6000.0)
        return {"schema":SCHEMA,"architecture":"96x128x64x5","available":bool(self.available),"rooms_trained":self.rooms_trained,"samples_trained":self.samples_trained,"mean_reward":round(self.mean_reward,4),"confidence":round(confidence,4),"max_candidate_vote":round(.65*confidence,4),"legacy_teacher_available":bool(self.legacy_teacher.available)}

def get_art_policy():
    global _POLICY
    with _LOCK:
        if _POLICY is None:_POLICY=ArtPolicy()
        return _POLICY

def _transition_targets(before,after,action,room_target=0.0,teacher_value=None):
    def delta(key,scale=1.0):return _signed((float(after.get(key,0) or 0)-float(before.get(key,0) or 0))/scale)
    meaningful=delta("meaningfulChangeRate");density_contrast=delta("densityContrast");regional_contrast=delta("regionalContrast");repetition_drop=-delta("repetition");direction_break=-delta("directionalUniformity");hierarchy_gain=delta("hierarchyStrength");focus_gain=delta("focalCommitment")
    revision=_clamp(before.get("revisionPotential",0));overwork=_clamp(before.get("overworkRisk",0));occupancy=_clamp(after.get("canvasOccupancy",0));mode=str(action.get("decisionMode") or "");editing=mode in {"ERASE","CONTRADICT","NEGATIVE_SPACE"}
    value=_signed((meaningful*.36+density_contrast*.16+regional_contrast*.16+repetition_drop*.12+direction_break*.08+hierarchy_gain*.12)*.78+room_target*.22)
    if teacher_value is not None:value=_signed(value*.82+float(teacher_value)*.18)
    tension=_signed(density_contrast*.38+regional_contrast*.42+delta("intersections",24.0)*.20)
    restraint=_signed(overwork*.72+max(0.0,occupancy-.48)*.55-max(0.0,.20-occupancy)*.30)
    edit_bias=_signed((revision*.65+overwork*.25) if editing else (revision*.25-.18))
    focus_commitment=_signed(focus_gain*.55+hierarchy_gain*.45)
    return [value,tension,restraint,edit_bias,focus_commitment]

def _final_room_reward(decisions):
    move=[r for r in decisions if isinstance(r,dict) and (r.get("action") or {}).get("intent")=="MOVE"]
    if not move:return 0.0
    o=(decisions[-1].get("observation") or {}) if decisions else {}
    coverage=_clamp(o.get("canvasOccupancy",0));meaningful=_clamp(o.get("meaningfulChangeRate",0));contrast=_clamp(o.get("densityContrast",0));regional=_clamp(o.get("regionalContrast",0));hierarchy=_clamp(o.get("hierarchyStrength",0));focus=_clamp(o.get("focalCommitment",0));overwork=_clamp(o.get("overworkRisk",0));repetition=_clamp(o.get("repetition",0))
    coverage_score=1.0 if .17<=coverage<=.56 else max(0.0,1.0-abs(coverage-.36)/.36)
    editing=min(1.0,sum(1 for r in move if (r.get("action") or {}).get("decisionMode") in {"ERASE","CONTRADICT","NEGATIVE_SPACE"})/max(1,len(move)*.10))
    return _clamp(coverage_score*.10+meaningful*.20+contrast*.12+regional*.13+hierarchy*.14+focus*.10+(1.0-repetition)*.08+editing*.08+(1.0-overwork)*.05)

def train_from_decisions(decisions,epochs=4):
    decisions=[r for r in (decisions or []) if isinstance(r,dict)];policy=get_art_policy();room_reward=_final_room_reward(decisions);room_target=_signed((room_reward-.5)*1.6,.8);samples=[]
    for index,record in enumerate(decisions[:-1]):
        action=record.get("action") or {}
        if action.get("intent")!="MOVE":continue
        before=record.get("observation") or {};after=decisions[index+1].get("observation") or {};history=decisions[max(0,index-8):index];mode=str(action.get("decisionMode") or "ABSTRACT_BUILD");context_pass=str(action.get("contextPass") or "GROUND");zebra=action.get("zebracnsActivity") or {};room_context={"artistic_temperament":action.get("artisticTemperament") or ""}
        x=features(before,action,mode,context_pass,zebra,history,room_context);teacher=None
        if policy.legacy_teacher.available:teacher=policy.legacy_teacher.predict(_legacy_features(before,action,mode,context_pass,zebra))
        samples.append((x,_transition_targets(before,after,action,room_target,teacher)))
    if samples:
        policy.train(samples,epochs=epochs);policy.rooms_trained+=1;n=policy.rooms_trained;policy.mean_reward=((policy.mean_reward*(n-1))+room_reward)/n;policy.save()
    result=policy.status();result["room_reward"]=round(room_reward,4);result["episode_samples"]=len(samples);return result
