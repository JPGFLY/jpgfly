"""Authoritative JPGFLY brain: one observed, stateful movement decision at a time."""
from __future__ import annotations

import json, logging, math, os, random, time, urllib.error, urllib.request
from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel, Field
from composition_engine import CompositionalDirector

LOGGER=logging.getLogger("jpgfly.brain")

PALETTE=("#ff3b30","#ff9500","#ffd60a","#32d74b","#00d4ff","#0a84ff","#5e5ce6","#bf5af2","#ff2d8d","#111111")
BRAIN_VERSION="JPGFLY-BRAIN/5.2-EXPERIENCE-LEARNING"
STYLES=("sweep","segmented","loop","spiral","curl","jitter","branch","cluster","echo","cross","contour","accent","bold","knot","fracture","orbit","web","coil","petal","lattice","hook","starburst","wave","zigzag","ribbon","vortex","rosette","maze","meander","blob","fan","helix","scallop","scribble")
BRUSHES=("ink_line","soft_paint","dry_brush","fine_pen","charcoal_grain","wash","stipple","splatter","subtractive")
TECHNIQUES=("continuous","hatching","cross_hatching","stippling","layered_glazing","overpainting","smudged_dragging","motif_repetition_different_brush","selective_erasure")
PHASES=("EXPLORATION","STRUCTURE","DEVELOPMENT","CONTRAST","REFINEMENT","RESOLUTION")
PHASE_STYLES={
    "EXPLORATION":("sweep","segmented","curl","contour","hook","petal","wave","ribbon","meander","blob","scribble"),
    "STRUCTURE":("bold","sweep","branch","cross","segmented","fracture","web","lattice","starburst","zigzag","maze","fan"),
    "DEVELOPMENT":("branch","echo","loop","spiral","contour","cluster","knot","orbit","web","coil","petal","vortex","rosette","helix","ribbon","blob"),
    "CONTRAST":("jitter","cross","segmented","bold","cluster","fracture","knot","lattice","starburst","zigzag","maze","scribble","fan"),
    "REFINEMENT":("contour","accent","echo","curl","jitter","orbit","web","coil","hook","petal","wave","scallop","rosette","meander"),
    "RESOLUTION":("accent","contour","cross","echo","sweep","knot","fracture","hook","starburst","wave","ribbon","scallop"),
}
TRANSFORMS=("repeat","distort","loose_mirror","extend","interrupt","cross","shrink","enlarge")
ARCHETYPES={
    "TENSION_FIELD":("cross","fracture","segmented","jitter","bold","lattice"),
    "ORBITAL_MEMORY":("orbit","loop","spiral","coil","knot","contour"),
    "BRANCHING_NETWORK":("branch","web","lattice","starburst","cross","sweep"),
    "QUIET_GEOMETRY":("contour","segmented","lattice","accent","hook","echo"),
    "GESTURAL_WEATHER":("sweep","curl","petal","jitter","cluster","bold"),
    "MOTIF_ECHO":("echo","loop","contour","spiral","hook","petal"),
    "AUTOMATIC_WEATHER":("scribble","wave","ribbon","meander","blob","jitter"),
    "GEOMETRIC_RUIN":("maze","zigzag","lattice","fan","segmented","cross"),
    "BIOMORPHIC_PORTAL":("vortex","rosette","helix","scallop","blob","coil"),
}
STRATEGY_TRANSFORMS={
    "SCOUT":("extend","distort","enlarge"),
    "BUILD":("repeat","extend","enlarge"),
    "REVISIT":("repeat","loose_mirror","shrink","enlarge"),
    "CONTRADICT":("interrupt","cross","distort"),
    "CONNECT":("extend","cross","repeat"),
    "ESCAPE":("distort","shrink","extend"),
    "RESOLVE":("repeat","shrink","loose_mirror"),
}

PALETTE_PRESETS={
    "TOXIC_NEON":("#a7ff1e","#ff2bb5","#3d7bff","#ffe74a","#101010"),
    "ASH_AND_BLOOD":("#101010","#8d8d93","#c8b78a","#8c1224","#9d4b2d"),
    "BRUISED_PASTEL":("#d892a4","#9e8ce0","#556aa8","#d4c39c","#705140","#101010"),
    "INSECT_WING":("#4f795b","#638baf","#d7a43a","#705140","#101010"),
    "BATHROOM_GRAFFITI":("#101010","#e33939","#5a8ccf","#8aa76e","#ff79b0"),
    "MOLDY_CANDY":("#72c8b8","#ff92c7","#8fd13f","#7f58d6","#e99a78","#101010"),
    "FUNERAL_NEON":("#101010","#ff3dae","#7f58d6","#57e0e6","#8c1224"),
    "COMIC_TRASH":("#111111","#e83b2f","#f4c83e","#2962cc","#3aa657","#e557aa"),
    "MUDDY_SIGNAL":("#221c18","#76543e","#8b6f47","#596b43","#9c4f3d","#42576e"),
    "NIGHT_CANDY":("#171221","#e144a0","#7c5cff","#27b7b2","#de8d35","#92bd47"),
    "MONO_DIRTY":("#111111","#3a3a3a","#66615b","#8a8176","#b06b52"),
}
MOODS=("MISCHIEVOUS","VULGAR","MELANCHOLIC","GROTESQUE","HORNY_STUPID","FUNERAL","PLAYFUL","PARANOID","FERAL","DREAMY","TRASHY","INSECTOID")
AUTONOMY_GOALS=("WANDER","OBSESS","CONNECT","AMPLIFY","SABOTAGE","JOKE","CALM")
COMPOSITION_MODES=("SWARM","CENTRAL_ICON","ORBITAL","DIAGONAL_ATTACK","BORDER_CRAWL","CORNER_NEST","TWO_ISLANDS","WEB_FIELD","PANEL_CHAOS","TOTEM")
SPATIAL_PROGRAMS=("SCATTERED_ISLANDS","CENTER_VOID","DIAGONAL_DESCENT","EDGE_RING","SPLIT_FIELD","VERTICAL_SPINE","HORIZONTAL_BAND","CORNER_PRESSURE")
STROKE_DIALECTS=("ANGULAR","ELASTIC","MICROGRAPHIC","MONUMENTAL","BROKEN","ORBITAL","SCRATCHED")
DURATION_PROFILES={
    "QUICK":(250,330),
    "STANDARD":(380,500),
    "LONG":(540,680),
    "OBSESSIVE":(720,850),
}
CONTENT_REGISTERS=("FORMAL","DOMESTIC","NATURAL","ARCHITECTURAL","COSMIC","MORTAL","ABSURD","BODILY")
DIALECT_STYLES={
    "ANGULAR":("segmented","cross","zigzag","lattice","maze","fracture"),
    "ELASTIC":("wave","ribbon","meander","sweep","curl","petal"),
    "MICROGRAPHIC":("accent","hook","contour","jitter","scallop","segmented"),
    "MONUMENTAL":("bold","sweep","web","starburst","branch","blob"),
    "BROKEN":("fracture","jitter","scribble","segmented","zigzag","cluster"),
    "ORBITAL":("orbit","loop","spiral","coil","vortex","rosette","helix"),
    "SCRATCHED":("scribble","jitter","fracture","contour","meander","hook"),
}
DETAIL_MODES=("SPARSE","BALANCED","DENSE","OBSESSIVE")
TEMPO_MODES=("TWITCHY","SMOOTH","INTERRUPTED","RITUALISTIC")
READABILITY_MODES=("LITERAL","STYLIZED","FRAGMENTED","ECHOED","HIDDEN","MUTATED")
SCENE_RELATIONS=("ISOLATED","CHASE","WATCHING","ORBITING","STACKED","NESTED","CROWD","PAIR","TOTEMIC")
SUBGOALS=("MAKE_BIG_ICON","MAKE_SMALL_SWARM","ADD_COMIC_NOISE","CONNECT_CLUSTERS","SABOTAGE_ORDER","REPEAT_FIGURE","LEAVE_NEGATIVE_SPACE","BUILD_WEIRD_SCENE")
FIGURATIVE_MOTIFS=("FLY","CAT_FACE","FISH","TV","GHOST","SNAIL","DUCK","MOUSE","SPIDER","MOTH","BEETLE","BIRD_HEAD","PHONE","KEY","CLOCK","EYEBALL","BOTTLE","WINDOW","LAMP","MASK","WEIRD_FACE","WING","FLOWER","MEAT_BLOB","BONE","CROWN","CIRCLE","TRIANGLE","SQUARE","RECTANGLE","DIAMOND","HEXAGON","OCTAGON","STAR","CRESCENT","SPIRAL_PORTAL","MAZE","GRID","CUBE","PYRAMID","ARCH","TUNNEL","HOUSE","DOOR","STAIRCASE","LADDER","TABLE","BED","CHAIR","ELEVATOR","CAGE","EGG","SHELL","HAND","FOOT","SKULL","HEART","MOUTH","NOSE","EAR","RIBCAGE","DOG_FACE","RABBIT_HEAD","BAT","SNAKE","WORM","JELLYFISH","OCTOPUS","CRAB","SUN","MOON","PLANET","COMET","CANDLE","CUP","FORK")
MOTIF_THEMES={
    "EYE":("loop","orbit","contour"),
    "WING":("petal","sweep","curl"),
    "TOOTH":("segmented","hook","contour"),
    "FLOWER":("petal","orbit","starburst"),
    "BONE":("segmented","hook","cross"),
    "CHAIR":("lattice","segmented","cross"),
    "SHOE":("contour","hook","sweep"),
    "UNDERWEAR":("loop","contour","hook"),
    "TRASH":("fracture","cluster","jitter"),
    "CROWN":("starburst","lattice","segmented"),
    "WEIRD_FACE":("loop","contour","jitter"),
    "CENSORED_MARK":("bold","cross","segmented"),
    "BANANA_CURVE":("curl","hook","sweep"),
    "PHALLIC_SPIRAL":("spiral","coil","hook"),
    "PAIRED_FLIES":("echo","orbit","loop"),
    "MATING_DANCE":("orbit","echo","curl"),
    "SLIME":("curl","cluster","jitter"),
    "MEAT_BLOB":("cluster","contour","knot"),
    "OOZE":("sweep","curl","contour"),
    "FLY":("orbit","loop","echo"),
    "CAT_FACE":("loop","hook","segmented"),
    "FISH":("loop","hook","sweep"),
    "TV":("lattice","segmented","cross"),
    "GHOST":("contour","curl","loop"),
    "SNAIL":("spiral","sweep","curl"),
    "DUCK":("loop","hook","contour"),
    "MOUSE":("loop","orbit","hook"),
    "SPIDER":("starburst","web","cross"),
    "MOTH":("petal","echo","orbit"),
    "BEETLE":("loop","segmented","lattice"),
    "BIRD_HEAD":("contour","hook","sweep"),
    "PHONE":("lattice","segmented","contour"),
    "KEY":("hook","loop","segmented"),
    "CLOCK":("orbit","loop","segmented"),
    "EYEBALL":("orbit","loop","contour"),
    "BOTTLE":("contour","segmented","hook"),
    "WINDOW":("lattice","cross","segmented"),
    "LAMP":("contour","hook","starburst"),
    "MASK":("loop","contour","jitter"),
    "CIRCLE":("loop","orbit","contour"),
    "TRIANGLE":("segmented","lattice","zigzag"),
    "SQUARE":("lattice","segmented","maze"),
    "RECTANGLE":("lattice","segmented","cross"),
    "DIAMOND":("lattice","zigzag","contour"),
    "HEXAGON":("lattice","segmented","orbit"),
    "OCTAGON":("lattice","segmented","contour"),
    "STAR":("starburst","zigzag","fan"),
    "CRESCENT":("contour","hook","scallop"),
    "SPIRAL_PORTAL":("vortex","spiral","coil"),
    "MAZE":("maze","segmented","zigzag"),
    "GRID":("lattice","cross","maze"),
    "CUBE":("lattice","segmented","cross"),
    "PYRAMID":("segmented","lattice","fan"),
    "ARCH":("contour","hook","segmented"),
    "TUNNEL":("contour","orbit","vortex"),
    "HOUSE":("lattice","segmented","contour"),
    "DOOR":("lattice","segmented","hook"),
    "STAIRCASE":("zigzag","segmented","maze"),
    "LADDER":("lattice","segmented","cross"),
    "TABLE":("lattice","segmented","cross"),
    "BED":("lattice","contour","segmented"),
    "CHAIR":("lattice","segmented","cross"),
    "ELEVATOR":("lattice","segmented","maze"),
    "CAGE":("lattice","cross","segmented"),
    "EGG":("contour","loop","blob"),
    "SHELL":("spiral","contour","scallop"),
    "HAND":("contour","branch","meander"),
    "FOOT":("contour","hook","sweep"),
    "SKULL":("contour","loop","fracture"),
    "HEART":("loop","contour","petal"),
    "MOUTH":("contour","loop","scallop"),
    "NOSE":("contour","hook","segmented"),
    "EAR":("contour","spiral","scallop"),
    "RIBCAGE":("branch","lattice","cross"),
    "DOG_FACE":("loop","contour","hook"),
    "RABBIT_HEAD":("loop","contour","petal"),
    "BAT":("petal","zigzag","sweep"),
    "SNAKE":("wave","meander","sweep"),
    "WORM":("wave","meander","scribble"),
    "JELLYFISH":("petal","branch","scallop"),
    "OCTOPUS":("branch","meander","blob"),
    "CRAB":("branch","cross","segmented"),
    "SUN":("starburst","fan","orbit"),
    "MOON":("contour","orbit","scallop"),
    "PLANET":("orbit","loop","sweep"),
    "COMET":("sweep","ribbon","fan"),
    "CANDLE":("contour","segmented","sweep"),
    "CUP":("contour","hook","segmented"),
    "FORK":("segmented","lattice","fan"),
}

SUBJECT_PROGRAMS={
    "INSECT_STUDY":("FLY","MOTH","BEETLE","SPIDER","WING","EYEBALL"),
    "FACE_AND_MASK":("WEIRD_FACE","MASK","EYEBALL","TOOTH","CROWN","SKULL","MOUTH","NOSE","EAR"),
    "ROOM_OBJECTS":("WINDOW","LAMP","CHAIR","TV","PHONE","CLOCK","BOTTLE","KEY","HOUSE","DOOR","STAIRCASE","LADDER","TABLE","BED","ELEVATOR","CAGE","CANDLE","CUP","FORK"),
    "BIOMORPHIC_BODY":("MEAT_BLOB","OOZE","SLIME","BONE","FLOWER","MATING_DANCE","HAND","FOOT","HEART","RIBCAGE","EGG","SHELL"),
    "ANIMAL_SIGNAL":("CAT_FACE","FISH","BIRD_HEAD","MOUSE","SNAIL","DUCK","DOG_FACE","RABBIT_HEAD","BAT","SNAKE","WORM","JELLYFISH","OCTOPUS","CRAB"),
    "GEOMETRIC_RITUAL":("CIRCLE","TRIANGLE","SQUARE","RECTANGLE","DIAMOND","HEXAGON","OCTAGON","STAR","GRID","CUBE","PYRAMID","ARCH","MAZE"),
    "COSMIC_ICON":("SUN","MOON","PLANET","COMET","CRESCENT","SPIRAL_PORTAL","TUNNEL","STAR"),
}

class BrainRequest(BaseModel): observation:dict[str,Any]

class BrainAction(BaseModel):
    intent:str; targetDirection:float; movementDistance:float=Field(ge=0,le=240); curvature:float=Field(ge=-4,le=4)
    speed:float=Field(ge=0,le=1); duration:int=Field(ge=0,le=2000); brushDown:bool; pressure:float=Field(ge=0,le=1)
    hesitation:int=Field(ge=0,le=1000); exploration:float=Field(ge=0,le=1); attentionTarget:dict[str,Any]
    eraseIntent:bool; movementStyle:str; relationshipToExistingMarks:str; motifReference:dict[str,Any]|None=None
    color:str="#111111"; confidence:float=Field(ge=0,le=1); reason:str; phase:str; evaluation:dict[str,Any]|None=None
    scale:float=Field(default=1,ge=.15,le=2.5); layerRole:str="PRIMARY"; motifTransform:str="none"
    branchingDepth:int=Field(default=0,ge=0,le=5); strokeCharacter:str="structural"; brushTool:str="ink_line"; technique:str="continuous"; motifHint:str="NONE"; autonomyGoal:str="WANDER"; paletteName:str=""; compositionMode:str="SWARM"; subgoal:str="ADD_COMIC_NOISE"; sceneRelation:str="ISOLATED"
    compositionPass:str="SCOUT"; regionTarget:int=Field(default=-1,ge=-1,le=11); macroIntent:str=""; subjectProgram:str=""

@dataclass(frozen=True)
class BrainLimits:
    max_session_duration_ms:int=600000; max_brain_decisions:int=800; max_physical_actions:int=800; max_consecutive_low_change:int=48

def clamp(v,lo,hi):return max(lo,min(hi,v))
def point(value,fallback):
    try:return [float(value[0]),float(value[1])] if len(value)==2 else list(fallback)
    except (TypeError,ValueError,IndexError):return list(fallback)
def angle_delta(a,b):return (b-a+math.pi)%math.tau-math.pi

def learned_choice(rng,pool,weights,strength,fallback=None):
    choices=[value for value in pool if float((weights or {}).get(value,0) or 0)>0]
    if choices and rng.random()<clamp(float(strength or 0),0,.4):
        ranked=[max(.0001,float(weights[value])) for value in choices]
        return rng.choices(choices,weights=ranked,k=1)[0]
    if fallback in pool:return fallback
    return rng.choice(tuple(pool))

@dataclass
class ProceduralFlyBrain:
    """A seeded fly personality with compositional memory and evolving plans."""
    seed:int; complexity:float=.96; mutation:float=.42; density:float=.64; experience:dict[str,Any]|None=None
    mode:str=field(init=False,default="LOCAL PROCEDURAL FLY BRAIN · STRUCTURED SUBJECT PAINTER")

    def __post_init__(self):
        self.complexity=clamp(float(self.complexity),.1,1);self.mutation=clamp(float(self.mutation),0,1);self.density=clamp(float(self.density),.1,1)
        self.rng=random.Random((int(self.seed)&0xffffffff)^0x9E3779B9);self.decision_count=0;self.heading=self.rng.random()*math.tau
        self.tendency=self.rng.choice(STYLES);self.style_counts={};self.motifs=[];self.evaluations=[];self.last_observation=None
        learned=self.experience or {};self.learning_strength=clamp(float(learned.get("strength",0) or 0),0,.4)
        self.learned_motifs=dict(learned.get("motifs") or {});self.learned_palettes=dict(learned.get("palettes") or {});self.learned_compositions=dict(learned.get("composition_modes") or {});self.learned_goals=dict(learned.get("goals") or {});self.learned_subjects=dict(learned.get("subject_programs") or {})
        self.recent_rooms=list(learned.get("recent_rooms") or [])[-6:]
        def recent_names(key):
            values=[]
            for room in self.recent_rooms[-4:]:
                raw=room.get(key)
                if isinstance(raw,str) and raw:values.append(raw)
                elif isinstance(raw,list):
                    for item in raw[:2]:
                        if isinstance(item,(list,tuple)) and item and item[0]:values.append(str(item[0]))
                        elif isinstance(item,str) and item:values.append(item)
            return values
        self._recent_compositions=recent_names("composition")
        self._recent_palettes=recent_names("palette")
        self._recent_subjects=recent_names("subject_program")
        self._recent_archetypes=recent_names("archetype")
        self._recent_spatial_programs=recent_names("spatial_program")
        self._recent_dialects=recent_names("stroke_dialect")
        self._recent_duration_profiles=recent_names("duration_profile")
        self._recent_content_registers=recent_names("content_register")
        def fresh(pool,recent,preferred=None,avoid_probability=.9):
            pool=list(pool);recent=set(recent)
            if preferred in pool and preferred not in recent:return preferred
            alternatives=[value for value in pool if value not in recent]
            if alternatives and self.rng.random()<avoid_probability:return self.rng.choice(alternatives)
            return self.rng.choice(pool)
        self.next_evaluation=self.rng.randint(6,9);self.branch_anchor=None;self.branch_remaining=0;self.branch_index=0;self.branch_cooldown=0
        self.phase_previous=None;self.gesture_remaining=0;self.relocation_target=None;self.zone_index=0
        self.spatial_program=fresh(SPATIAL_PROGRAMS,self._recent_spatial_programs,avoid_probability=.96)
        self.stroke_dialect=fresh(STROKE_DIALECTS,self._recent_dialects,avoid_probability=.96)
        self.duration_profile=fresh(tuple(DURATION_PROFILES),self._recent_duration_profiles,avoid_probability=.92)
        self.content_register=fresh(CONTENT_REGISTERS,self._recent_content_registers,avoid_probability=.92)
        self.zone_anchors=self._build_zone_anchors(self.spatial_program)
        self.archetype=fresh(tuple(ARCHETYPES),self._recent_archetypes,avoid_probability=.88);self.strategy="SCOUT";self.strategy_hold=0;self.strategy_history=[]
        self.anchor_visits=[0 for _ in self.zone_anchors]
        mood_pool=list(MOODS)
        if self.content_register not in ("ABSURD","BODILY"):
            mood_pool=[m for m in mood_pool if m not in ("HORNY_STUPID","VULGAR")]
        self.mood=self.rng.choice(mood_pool)
        self.humor_level=(.42+self.rng.random()*.35) if self.content_register=="ABSURD" else self.rng.random()*.18
        self.suggestiveness=(.38+self.rng.random()*.4) if self.content_register=="BODILY" else self.rng.random()*.14
        self.grotesque_level=(.36+self.rng.random()*.48) if self.content_register in ("BODILY","MORTAL") else self.rng.random()*.42
        self.figurative_level=.28+self.rng.random()*.44
        learned_composition=learned_choice(self.rng,COMPOSITION_MODES,self.learned_compositions,self.learning_strength)
        self.composition_mode=fresh(COMPOSITION_MODES,self._recent_compositions,learned_composition,.94);self.detail_mode=self.rng.choice(DETAIL_MODES);self.tempo_mode=self.rng.choice(TEMPO_MODES);self.readability_mode=self.rng.choice(READABILITY_MODES);self.scene_relation=self.rng.choice(SCENE_RELATIONS)
        self.subgoal=self.rng.choice(SUBGOALS);self.subgoal_hold=self.rng.randint(24,48);self.scene_anchor=self.rng.choice(self.zone_anchors);self.scene_partner=self.rng.choice(self.zone_anchors)
        detail_multiplier={"SPARSE":.62,"BALANCED":.88,"DENSE":1.08,"OBSESSIVE":1.22}[self.detail_mode];self.density=clamp(self.density*detail_multiplier,.1,1)
        mood_palettes={"HORNY_STUPID":("BATHROOM_GRAFFITI","MOLDY_CANDY","TOXIC_NEON","NIGHT_CANDY"),"GROTESQUE":("ASH_AND_BLOOD","MOLDY_CANDY","INSECT_WING","MUDDY_SIGNAL"),"FUNERAL":("FUNERAL_NEON","ASH_AND_BLOOD","MONO_DIRTY"),"PLAYFUL":("MOLDY_CANDY","TOXIC_NEON","BRUISED_PASTEL","COMIC_TRASH"),"MELANCHOLIC":("BRUISED_PASTEL","ASH_AND_BLOOD","MONO_DIRTY"),"TRASHY":("COMIC_TRASH","BATHROOM_GRAFFITI","MUDDY_SIGNAL"),"FERAL":("MUDDY_SIGNAL","ASH_AND_BLOOD","TOXIC_NEON"),"DREAMY":("BRUISED_PASTEL","NIGHT_CANDY","INSECT_WING"),"INSECTOID":("INSECT_WING","TOXIC_NEON","MUDDY_SIGNAL")}
        base_palette=self.rng.choice(mood_palettes.get(self.mood,tuple(PALETTE_PRESETS)));learned_palette=learned_choice(self.rng,tuple(PALETTE_PRESETS),self.learned_palettes,self.learning_strength,base_palette);self.palette_name=fresh(tuple(PALETTE_PRESETS),self._recent_palettes,learned_palette,.92);self.palette=PALETTE_PRESETS[self.palette_name]
        learned_subject=learned_choice(self.rng,tuple(SUBJECT_PROGRAMS),self.learned_subjects,self.learning_strength);self.subject_program_name=fresh(tuple(SUBJECT_PROGRAMS),self._recent_subjects,learned_subject,.9);self.subject_program=SUBJECT_PROGRAMS[self.subject_program_name];self.motif_theme=learned_choice(self.rng,self.subject_program,self.learned_motifs,self.learning_strength);self.motif_theme_hold=self.rng.randint(18,34);self.next_intrusion=self.rng.randint(16,30);self.motif_intrusion=False
        self.personality={"chaos":.12+self.rng.random()*.5,"order":.42+self.rng.random()*.5,"crowdAvoidance":.52+self.rng.random()*.4,"returnBias":.62+self.rng.random()*.3,"eraseBias":.10+self.rng.random()*.16,"editBias":.42+self.rng.random()*.38,"patience":.68+self.rng.random()*.28,"scaleBias":.28+self.rng.random()*.6,"contrastBias":.42+self.rng.random()*.48}
        self.drives={"curiosity":.45+self.rng.random()*.55,"stubbornness":.25+self.rng.random()*.7,"mischief":.45+self.rng.random()*.55,"novelty":.4+self.rng.random()*.6,"coherence":.25+self.rng.random()*.7}
        self.goal=learned_choice(self.rng,AUTONOMY_GOALS,self.learned_goals,self.learning_strength,"WANDER");self.last_goal=None;self.goal_hold=0;self.boredom=0.0;self.surprise_urge=.25+self.rng.random()*.55;self.palette_shifts=0;self.goal_history=[]
        self.next_joke=self.rng.randint(72,150);self.joke_count=0
        low,high=DURATION_PROFILES[self.duration_profile]
        self.desired_decisions=self.rng.randint(low,high)
        self.target_families=min(len(STYLES),8+round(self.complexity*7));self.primary_anchor=[self.rng.uniform(245,555),self.rng.uniform(145,355)]
        self.current_plan=None
        self.director=CompositionalDirector(self.seed,self.composition_mode,self.archetype,self.complexity,self.mutation,self.density)

    def _build_zone_anchors(self,program):
        r=self.rng
        if program=="CENTER_VOID":
            return [[400+math.cos(i*math.tau/6)*r.uniform(145,250),250+math.sin(i*math.tau/6)*r.uniform(95,165)] for i in range(6)]
        if program=="DIAGONAL_DESCENT":
            return [[90+i*125+r.uniform(-22,22),75+i*62+r.uniform(-25,25)] for i in range(6)]
        if program=="EDGE_RING":
            return [[70,90],[400,55],[730,100],[735,405],[400,445],[65,400]]
        if program=="SPLIT_FIELD":
            return [[r.uniform(70,275),r.uniform(70,430)] for _ in range(3)]+[[r.uniform(525,735),r.uniform(70,430)] for _ in range(3)]
        if program=="VERTICAL_SPINE":
            return [[r.uniform(335,465),70+i*72+r.uniform(-18,18)] for i in range(6)]
        if program=="HORIZONTAL_BAND":
            return [[75+i*130+r.uniform(-18,18),r.uniform(185,315)] for i in range(6)]
        if program=="CORNER_PRESSURE":
            return [[75,70],[725,75],[80,425],[720,420],[r.uniform(250,350),r.uniform(190,310)],[r.uniform(450,550),r.uniform(190,310)]]
        # SCATTERED_ISLANDS: deliberately irregular and not locked to the old six-cell grid.
        points=[]
        attempts=0
        while len(points)<6 and attempts<120:
            attempts+=1;candidate=[r.uniform(65,735),r.uniform(55,445)]
            if all(math.dist(candidate,old)>85 for old in points):points.append(candidate)
        while len(points)<6:points.append([r.uniform(65,735),r.uniform(55,445)])
        return points

    def phase(self):
        progress=clamp(self.decision_count/max(1,self.desired_decisions),0,1)
        return PHASES[min(5,int(progress*6))]

    def evaluate(self,o,limits):
        coverage=float(o.get("canvasOccupancy",0));target=.24+self.density*.42;fit=1-min(1,abs(coverage-target)/max(.1,target))
        families=o.get("familyCounts",{}) or {};variety=min(1,len(families)/max(1,self.target_families));balance=float(o.get("densityBalance",1))
        direction_variety=1-float(o.get("directionalUniformity",0));density_contrast=float(o.get("densityContrast",0));meaning=float(o.get("meaningfulChangeRate",1));repeat=float(o.get("repetition",0))
        low=int(o.get("consecutiveLowChange",0));noise=min(1,low/max(1,limits.max_consecutive_low_change));maturity=min(1,self.decision_count/max(1,self.desired_decisions))
        director=self.director.evaluate(o,self.style_counts,int(o.get("intersections",0) or 0),len(self.motifs))
        milestone_bonus=director.milestone_ratio*.18
        readiness=clamp(fit*.11+variety*.12+balance*.07+direction_variety*.08+density_contrast*.08+meaning*.08+maturity*.22+director.composition_score*.20+milestone_bonus-max(0,repeat-.42)*.16-noise*.14,0,1)
        result={"atDecision":self.decision_count,"coverageFit":round(fit,3),"variety":round(variety,3),"balance":round(balance,3),"directionVariety":round(direction_variety,3),"densityContrast":round(density_contrast,3),"meaningfulChange":round(meaning,3),"repetition":round(repeat,3),"noisePenalty":round(noise,3),"compositionScore":director.composition_score,"regionalSpread":director.regional_spread,"protectedSpace":director.protected_space,"directorNeed":director.need,"painterMilestones":director.milestone_ratio,"finishReady":director.finish_ready,"readiness":round(readiness,3),"summary":"The painting has passed through interruption, return and editing." if director.finish_ready and readiness>.76 else "The painter is still developing and revising the room." if readiness>.53 else "The painter still sees unresolved space."}
        self.evaluations.append(result);return result

    def finish(self,o,limits,reason=""):
        plan=self.current_plan or {"pass":"RESOLVE","target_region":-1,"macro_intent":"RESOLVE:RESOLVE"}
        return BrainAction(intent="FINISH_ARTWORK",targetDirection=self.heading,movementDistance=0,curvature=0,speed=0,duration=0,brushDown=False,pressure=0,hesitation=0,exploration=0,attentionTarget={"kind":"whole_canvas","point":point(o.get("focalArea"),[400,250])},eraseIntent=False,movementStyle=self.tendency,relationshipToExistingMarks="final_evaluation",color=self.choose_color("RESOLUTION"),confidence=1,reason=reason or "FLY_DECLARED_LAYERED_COMPOSITION_COMPLETE",phase="RESOLUTION",evaluation=self.evaluate(o,limits),scale=1,layerRole="TERTIARY",strokeCharacter="final",motifHint="NONE",autonomyGoal=self.goal,paletteName=self.palette_name,compositionMode=self.composition_mode,subgoal=self.subgoal,sceneRelation=self.scene_relation,compositionPass=plan.get("pass","RESOLVE"),regionTarget=int(plan.get("target_region",-1)),macroIntent=plan.get("macro_intent","RESOLVE:RESOLVE"))

    def hard_limit(self,o,l):
        if int(o.get("elapsedDrawingTime",0))>=l.max_session_duration_ms:return "SAFETY_MAX_SESSION_DURATION"
        if self.decision_count>=l.max_brain_decisions:return "SAFETY_MAX_BRAIN_DECISIONS"
        if int(o.get("physicalActionCount",0))>=l.max_physical_actions:return "SAFETY_MAX_PHYSICAL_ACTIONS"
        if int(o.get("consecutiveLowChange",0))>=l.max_consecutive_low_change:return "SAFETY_MAX_ACTIONS_WITHOUT_MEANINGFUL_CHANGE"
        return ""

    def remember_result(self,o):
        if not self.last_observation or not self.motifs:return
        delta_cross=int(o.get("intersections",0))-int(self.last_observation.get("intersections",0));delta_cover=float(o.get("canvasOccupancy",0))-float(self.last_observation.get("canvasOccupancy",0))
        self.motifs[-1]["interest"]=round(clamp(self.motifs[-1]["interest"]+delta_cross*.16+max(0,delta_cover)*4,0,2),3)

    def choose_goal(self,phase,o,evaluation=None):
        repetition=float(o.get("repetition",0));uniform=float(o.get("directionalUniformity",0));density=float(o.get("localDensity",0));contrast=float(o.get("densityContrast",0));low=int(o.get("consecutiveLowChange",0))
        scores={goal:.1+self.rng.random()*.12 for goal in AUTONOMY_GOALS}
        for learned_goal,weight in self.learned_goals.items():
            if learned_goal in scores:scores[learned_goal]+=self.learning_strength*float(weight or 0)*1.35
        scores["WANDER"]+=self.drives["curiosity"]*(.55 if density<.55 else .18)+self.drives["novelty"]*.25
        scores["OBSESS"]+=self.drives["stubbornness"]*(.55 if self.motifs else .08)+(contrast*.25)
        scores["CONNECT"]+=(1-contrast)*.45+self.drives["coherence"]*.35
        scores["AMPLIFY"]+=(1-density)*.32+self.personality["contrastBias"]*.28
        scores["SABOTAGE"]+=self.drives["mischief"]*(repetition*.55+uniform*.45+self.boredom*.7)
        scores["JOKE"]+=self.drives["mischief"]*.55+self.humor_level*.45+self.boredom*.5
        scores["CALM"]+=density*.48+self.drives["coherence"]*.25+(low*.025)
        if self.content_register=="ABSURD" and self.mood in ("PLAYFUL","MISCHIEVOUS","TRASHY"):scores["JOKE"]+=.42
        elif self.content_register!="ABSURD":scores["JOKE"]*=.38
        if self.mood in ("GROTESQUE","PARANOID"):scores["SABOTAGE"]+=.34
        if phase=="EXPLORATION":scores["WANDER"]+=.65
        if phase=="RESOLUTION":scores["CALM"]+=.8
        if evaluation and evaluation.get("readiness",0)>.72:scores["CALM"]+=.35
        return max(scores,key=scores.get)

    def maybe_shift_palette(self):
        if self.palette_shifts>=1:return
        if self.goal not in ("SABOTAGE","JOKE","WANDER"):return
        chance=.015+self.surprise_urge*.05+self.boredom*.06
        if self.rng.random()>=chance:return
        choices=[name for name in PALETTE_PRESETS if name!=self.palette_name]
        if not choices:return
        self.palette_name=self.rng.choice(choices);self.palette=PALETTE_PRESETS[self.palette_name];self.palette_shifts+=1
        self.surprise_urge=clamp(self.surprise_urge-.22,0,1)

    def update_autonomy(self,phase,o,evaluation=None):
        repetition=float(o.get("repetition",0));uniform=float(o.get("directionalUniformity",0));contrast=float(o.get("densityContrast",0));low=int(o.get("consecutiveLowChange",0))
        boredom_signal=repetition*.44+uniform*.32+min(1,low/8)*.24-contrast*.18
        self.boredom=clamp(self.boredom*.72+boredom_signal*.42,0,1)
        self.surprise_urge=clamp(self.surprise_urge+.025+self.boredom*.045,0,1)
        self.goal_hold-=1
        change=self.goal_hold<=0 or self.boredom>.72 or (evaluation is not None and self.rng.random()<.55)
        if change:
            previous=self.goal;self.goal=self.choose_goal(phase,o,evaluation);self.goal_hold=self.rng.randint(4,10)
            if self.goal!=previous:
                self.last_goal=previous;self.goal_history.append({"decision":self.decision_count,"from":previous,"to":self.goal,"phase":phase})
                self.boredom*=.55
        self.maybe_shift_palette()

    def choose_strategy(self,phase,o):
        # Multi-action artistic strategy: persistent internal goals steer several marks at a time.
        if self.current_plan and self.current_plan.get("strategy") and self.rng.random()<.72:
            return self.current_plan["strategy"]
        if phase=="EXPLORATION" and self.goal not in ("JOKE","SABOTAGE"):return "SCOUT"
        if phase=="RESOLUTION":return "RESOLVE"
        if self.goal=="OBSESS":return "REVISIT"
        if self.goal=="CONNECT":return "CONNECT"
        if self.goal=="SABOTAGE":return "CONTRADICT"
        if self.goal=="JOKE":return self.rng.choice(("CONTRADICT","BUILD","REVISIT"))
        if self.goal=="AMPLIFY":return "BUILD"
        if self.goal=="CALM":return self.rng.choice(("ESCAPE","REVISIT"))
        if self.goal=="WANDER" and self.rng.random()<.62:return self.rng.choice(("SCOUT","ESCAPE","CONNECT"))
        crowded=int(o.get("nearbyLines",0))>5 or float(o.get("localDensity",0))>.76
        repetition=float(o.get("repetition",0));uniform=float(o.get("directionalUniformity",0));contrast=float(o.get("densityContrast",0))
        if crowded:return self.rng.choice(("ESCAPE","CONTRADICT","REVISIT"))
        if repetition>.48 or uniform>.62:return self.rng.choice(("CONTRADICT","CONNECT","ESCAPE"))
        if contrast<.14 and phase in ("DEVELOPMENT","CONTRAST"):return self.rng.choice(("CONNECT","CONTRADICT","BUILD"))
        if self.motifs and phase in ("DEVELOPMENT","REFINEMENT") and self.rng.random()<self.personality["returnBias"]:return self.rng.choice(("REVISIT","CONNECT","BUILD"))
        if self.archetype=="BRANCHING_NETWORK":return self.rng.choice(("CONNECT","BUILD","CONTRADICT"))
        if self.archetype=="ORBITAL_MEMORY":return self.rng.choice(("REVISIT","BUILD","CONNECT"))
        if self.archetype=="TENSION_FIELD":return self.rng.choice(("CONTRADICT","BUILD","ESCAPE"))
        return self.rng.choice(("BUILD","CONNECT","REVISIT"))
    def choose_color(self,phase):
        palette=list(self.palette)
        if phase=="CONTRAST":
            emphatic=[color for color in palette if color.lower() in ("#101010","#8c1224","#a7ff1e","#ff3dae","#3d7bff","#ffe74a")]
            if emphatic and self.rng.random()<.58:return self.rng.choice(emphatic)
        if phase=="RESOLUTION" and self.rng.random()<.6:return self.rng.choice(palette[:max(2,min(3,len(palette)))])
        return self.rng.choice(palette)

    def choose_theme(self,phase):
        self.motif_theme_hold-=1
        suggestive=("PHALLIC_SPIRAL","PAIRED_FLIES","MATING_DANCE","BANANA_CURVE","UNDERWEAR")
        grotesque=("SLIME","MEAT_BLOB","OOZE","BONE","TOOTH")
        comic=("WEIRD_FACE","CROWN","CHAIR","SHOE","TRASH","CENSORED_MARK","BANANA_CURVE")+FIGURATIVE_MOTIFS
        if self.content_register=="ABSURD" and self.decision_count>=self.next_joke and phase!="RESOLUTION":
            pool=list(FIGURATIVE_MOTIFS)*4+list(comic)*2
            if self.suggestiveness>.42:pool+=list(suggestive)
            if self.grotesque_level>.5:pool+=list(grotesque)
            self.motif_theme=self.rng.choice(pool);self.motif_theme_hold=self.rng.randint(10,18);self.motif_intrusion=True;self.joke_count+=1
            self.next_joke=self.decision_count+self.rng.randint(80,150)
        elif self.content_register=="ABSURD" and self.goal=="JOKE" and phase!="RESOLUTION" and self.rng.random()<.18:
            pool=list(FIGURATIVE_MOTIFS)*4+list(comic)*2+list(suggestive if self.suggestiveness>.35 else ())
            self.motif_theme=self.rng.choice(pool);self.motif_theme_hold=self.rng.randint(8,14);self.motif_intrusion=True
        elif self.decision_count>=self.next_intrusion and phase not in ("EXPLORATION","RESOLUTION"):
            pool=list(self.subject_program)
            if self.content_register=="ABSURD":pool+=list(comic)
            if self.content_register=="BODILY" and self.suggestiveness>.48:pool+=list(suggestive)
            if self.content_register in ("BODILY","MORTAL") and self.grotesque_level>.48:pool+=list(grotesque)
            self.motif_theme=self.rng.choice(pool);self.motif_theme_hold=self.rng.randint(10,18);self.motif_intrusion=True
            self.next_intrusion=self.decision_count+self.rng.randint(42,78)
        elif self.motif_theme_hold<=0 or (phase in ("DEVELOPMENT","CONTRAST","REFINEMENT") and self.rng.random()<.1):
            self.motif_intrusion=False
            if self.content_register=="BODILY" and self.suggestiveness>.66 and self.rng.random()<self.suggestiveness*.55:self.motif_theme=self.rng.choice(suggestive)
            elif self.grotesque_level>.62 and self.rng.random()<self.grotesque_level:self.motif_theme=self.rng.choice(grotesque)
            elif self.content_register=="ABSURD" and self.humor_level>.55 and self.rng.random()<self.humor_level*.55:self.motif_theme=self.rng.choice(comic)
            else:
                pool=self.subject_program if self.rng.random()<.72 else tuple(MOTIF_THEMES)
                self.motif_theme=learned_choice(self.rng,pool,self.learned_motifs,self.learning_strength)
            self.motif_theme_hold=self.rng.randint(14,28)
        return self.motif_theme

    def choose_style(self,phase,o):
        allowed=list(PHASE_STYLES[phase]);used=set(self.style_counts);needed=max(2,round(self.target_families*min(1,.18+self.decision_count/max(1,self.desired_decisions))))
        dialect=[style for style in DIALECT_STYLES.get(self.stroke_dialect,()) if style in allowed]
        if dialect and self.rng.random()<.34:
            underused=sorted(dialect,key=lambda style:self.style_counts.get(style,0))
            return self.rng.choice(underused[:max(1,min(3,len(underused)))])
        if self.current_plan:
            preferred=self.current_plan.get("preferred_style")
            pool=[style for style in self.current_plan.get("style_pool",()) if style in allowed]
            if preferred in allowed and self.rng.random()<.58:return preferred
            if pool and self.rng.random()<.46:return self.rng.choice(pool)
        theme=self.choose_theme(phase);themed=[style for style in MOTIF_THEMES[theme] if style in allowed]
        if theme in self.subject_program and themed and self.rng.random()<.74:return self.rng.choice(themed)
        if self.motif_intrusion and theme in FIGURATIVE_MOTIFS and themed:return self.rng.choice(themed)
        unused=[style for style in allowed if style not in used] or [style for style in STYLES if style not in used]
        if len(used)<needed and unused:return self.rng.choice(unused)
        strategic={"CONTRADICT":("cross","fracture","segmented","jitter","starburst","zigzag","maze","scribble"),"CONNECT":("web","branch","lattice","sweep","cross","ribbon","meander"),"REVISIT":("echo","contour","loop","spiral","coil","rosette","vortex","helix"),"ESCAPE":("accent","sweep","hook","curl","wave","ribbon","fan"),"RESOLVE":("accent","contour","echo","hook","scallop","wave")}.get(self.strategy,())
        preferred=[style for style in strategic if style in allowed]
        archetypal=[style for style in ARCHETYPES[self.archetype] if style in allowed]
        if theme in FIGURATIVE_MOTIFS and themed and (self.motif_intrusion or self.goal=="JOKE" or self.subgoal in ("MAKE_BIG_ICON","MAKE_SMALL_SWARM","REPEAT_FIGURE","BUILD_WEIRD_SCENE") or self.readability_mode=="LITERAL"):return self.rng.choice(themed)
        if themed and self.rng.random()<self.figurative_level:return self.rng.choice(themed)
        if preferred and self.rng.random()<.52:return self.rng.choice(preferred)
        if archetypal and self.rng.random()<.58:return self.rng.choice(archetypal)
        if self.style_counts and max(self.style_counts.values())>max(3,self.decision_count*.19):return min(allowed,key=lambda family:self.style_counts.get(family,0))
        if float(o.get("directionalUniformity",0))>.58:return self.rng.choice(("cross","segmented","branch"))
        if float(o.get("densityContrast",0))<.16 and phase not in ("EXPLORATION","RESOLUTION"):return self.rng.choice(("cluster","bold","accent"))
        if self.rng.random()<.26+self.complexity*.38:return self.rng.choice(allowed)
        return self.tendency if self.tendency in STYLES else self.rng.choice(allowed)

    def choose_motif(self):
        if not self.motifs:return None
        pool=sorted(self.motifs,key=lambda m:(m["interest"],m["decision"]),reverse=True)[:10]
        if self.strategy=="REVISIT":return pool[0]
        if self.strategy=="CONTRADICT":return min(pool,key=lambda m:m["decision"])
        if self.strategy=="CONNECT" and len(pool)>1:return self.rng.choice(pool[:min(5,len(pool))])
        return self.rng.choice(pool)

    def choose_zone(self,phase,o):
        empty=point(o.get("negativeSpace"),[400,250]);focal=point(o.get("focalArea"),self.primary_anchor)
        if self.current_plan and self.current_plan.get("target_point") and self.rng.random()<.78:
            target=self.current_plan["target_point"]
            return [clamp(float(target[0])+self.rng.uniform(-16,16),45,755),clamp(float(target[1])+self.rng.uniform(-14,14),45,455)]
        if self.subgoal=="LEAVE_NEGATIVE_SPACE":target=empty
        elif self.composition_mode=="CENTRAL_ICON":target=self.primary_anchor
        elif self.composition_mode=="CORNER_NEST":target=self.zone_anchors[0 if self.seed%2==0 else -1]
        elif self.composition_mode=="TWO_ISLANDS":target=self.zone_anchors[1 if self.zone_index%2==0 else 4];self.zone_index+=1
        elif self.composition_mode=="TOTEM":target=[400,self.rng.choice((90,160,250,340,420))]
        elif self.composition_mode=="BORDER_CRAWL":target=self.rng.choice(([55,self.rng.uniform(55,445)],[745,self.rng.uniform(55,445)],[self.rng.uniform(55,745),55],[self.rng.uniform(55,745),445]))
        elif self.composition_mode=="DIAGONAL_ATTACK":target=[clamp(90+(self.decision_count%80)*8,70,730),clamp(430-(self.decision_count%80)*4.5,70,430)]
        elif self.subgoal=="BUILD_WEIRD_SCENE":target=self.scene_anchor if self.decision_count%2==0 else self.scene_partner
        elif self.strategy=="ESCAPE":target=empty
        elif self.strategy=="REVISIT" and self.motifs:target=point(self.choose_motif()["point"],focal)
        elif self.strategy=="CONTRADICT":
            index=max(range(len(self.zone_anchors)),key=lambda i:math.dist(self.zone_anchors[i],focal));target=self.zone_anchors[index];self.anchor_visits[index]+=1
        elif self.strategy=="CONNECT":
            index=min(range(len(self.zone_anchors)),key=lambda i:self.anchor_visits[i]);target=self.zone_anchors[index];self.anchor_visits[index]+=1
        elif phase=="EXPLORATION":
            index=self.zone_index%len(self.zone_anchors);target=self.zone_anchors[index];self.anchor_visits[index]+=1;self.zone_index+=1
        elif phase=="STRUCTURE":target=self.primary_anchor if self.zone_index%2 else focal;self.zone_index+=1
        elif phase in ("DEVELOPMENT","REFINEMENT") and self.motifs:target=point(self.choose_motif()["point"],focal)
        elif phase=="CONTRAST":target=focal if int(o.get("intersections",0))<5 else empty
        else:target=empty
        return [clamp(float(target[0])+self.rng.uniform(-28,28),45,755),clamp(float(target[1])+self.rng.uniform(-24,24),45,455)]

    def relocation_action(self,target,phase,pos,evaluation=None):
        dx,dy=target[0]-pos[0],target[1]-pos[1];distance=math.hypot(dx,dy);heading=math.atan2(dy,dx);movement=min(210,max(18,distance-28));self.heading=heading
        if distance<=235:self.relocation_target=None;self.gesture_remaining=self.rng.randint(14,26)
        relocation_thoughts={"EXPLORATION":"Lift. Test a remote patch of silence.","STRUCTURE":"Lift. Re-enter beside the emerging spine.","DEVELOPMENT":"Lift. Carry the memory into another zone.","CONTRAST":"Lift. Put distance between these competing structures.","REFINEMENT":"Lift. Return from a less expected angle.","RESOLUTION":"Lift. Search the remaining unclaimed edge."}
        return BrainAction(intent="MOVE",targetDirection=round(heading,3),movementDistance=round(movement,3),curvature=0,speed=.58,duration=round(180+movement*2.2),brushDown=False,pressure=0,hesitation=self.rng.randint(18,55),exploration=.98,attentionTarget={"kind":"relocation_zone","point":[round(v,3) for v in target]},eraseIntent=False,movementStyle="accent",relationshipToExistingMarks="lift_and_relocate_to_new_structure",motifReference=None,color=self.choose_color(phase),confidence=.96,reason=relocation_thoughts[phase],phase=phase,evaluation=evaluation,scale=round(clamp(distance/150,.4,2),3),layerRole="PRIMARY" if phase in ("EXPLORATION","STRUCTURE") else "SECONDARY" if phase in ("DEVELOPMENT","CONTRAST") else "TERTIARY",motifTransform="none",branchingDepth=0,strokeCharacter="relocation",motifHint="NONE",autonomyGoal=self.goal,paletteName=self.palette_name,compositionMode=self.composition_mode,subgoal=self.subgoal,sceneRelation=self.scene_relation)

    def public_reason(self,phase,layer,style,relation,transform,o,erase,strategy):
        # Public-facing comments describe observable strategy, not hidden reasoning.
        theme_comments={
            "EYE":"An eye-shaped loop appeared. I am letting it watch the rest.",
            "WING":"This mark started behaving like a wing, so I gave it room.",
            "TOOTH":"The edge looked too polite. Give it a tooth.",
            "FLOWER":"This almost became a flower. Almost is more interesting.",
            "BONE":"A bone-like hinge gives the soft marks something to fight.",
            "CHAIR":"It vaguely looks like furniture now. That is its problem.",
            "SHOE":"A shoe-shaped accident appeared. I am not fixing it.",
            "UNDERWEAR":"This contour has embarrassing underwear energy. Keep it.",
            "TRASH":"The composition needed some trash in the expensive neighborhood.",
            "CROWN":"A ridiculous little crown is trying to become important.",
            "WEIRD_FACE":"A face appeared by accident and now it gets to stay.",
            "CENSORED_MARK":"The drawing wanted censorship, so I mocked it with a bar.",
            "BANANA_CURVE":"This curve is too stupid not to keep.",
            "PHALLIC_SPIRAL":"The spiral looks suspiciously indecent, which makes it useful.",
            "PAIRED_FLIES":"Two fly-like loops found each other. I let them tangle.",
            "MATING_DANCE":"This almost became fly courtship. I kept the awkward orbit.",
            "SLIME":"The composition needed something wet and rude.",
            "MEAT_BLOB":"A soft ugly blob makes the structure less obedient.",
            "OOZE":"Let this edge ooze instead of behaving like a line.",
            "FLY":"I drew a fly because apparently one fly was not enough.",
            "CAT_FACE":"A cat showed up. It looks judgmental. Good.",
            "FISH":"This fish has no business being here, so it stays.",
            "TV":"I put a tiny television in the composition. It has no signal.",
            "GHOST":"A ghost wandered into the drawing. I am not charging rent.",
            "SNAIL":"The snail is slower than the composition and somehow winning.",
            "DUCK":"A duck happened. I have decided this is serious art.",
            "MOUSE":"There is a mouse in here now. Nobody panic.",
            "SPIDER":"The spider makes the drawing less trustworthy.",
            "MOTH":"The moth wanted the light, so I gave it the page.",
            "BEETLE":"This beetle is built like a tiny armored mistake.",
            "BIRD_HEAD":"A bird head arrived looking more confident than I am.",
            "PHONE":"A phone appeared. It has bad vibes.",
            "KEY":"A key wandered in. It opens nothing I respect.",
            "CLOCK":"The clock is wrong on purpose.",
            "EYEBALL":"Another eye. Apparently the drawing needs supervision.",
            "BOTTLE":"A bottle showed up and immediately lowered the tone.",
            "WINDOW":"I drew a window into nowhere. Excellent.",
            "LAMP":"The lamp is illuminating absolutely nothing useful.",
            "MASK":"This mask looks suspicious. I approve.",
        }
        goal_comments={"WANDER":"I got curious and left the obvious route.","OBSESS":"I am not done with this shape yet.","CONNECT":"These parts should know each other.","AMPLIFY":"This needs to become louder.","SABOTAGE":"It was becoming predictable, so I interfered.","JOKE":"This got too serious. I fixed that badly.","CALM":"Enough noise. Tighten the structure."}
        if self.content_register=="ABSURD" and self.rng.random()<.1:return goal_comments.get(self.goal,"Keep moving.")
        if self.content_register=="ABSURD" and self.motif_intrusion and self.rng.random()<.52:return theme_comments.get(self.motif_theme,"This mark is strange enough to keep.")
        if self.content_register=="ABSURD" and self.rng.random()<(.04+self.humor_level*.08):return theme_comments.get(self.motif_theme,"This mark is strange enough to keep.")
        if self.content_register=="ABSURD" and self.humor_level>.72 and self.rng.random()<.08:return self.rng.choice(("The composition needed dignity. I disagreed.","It was getting too tasteful.","The center was behaving, so I made it worse."))
        strategic={
            "SCOUT":(f"Test a {style} in territory I have barely touched.","Probe another zone before the composition settles."),
            "BUILD":(f"Strengthen the current structure with a {style}.",f"Give the composition another load-bearing {style}."),
            "REVISIT":(f"Return to a remembered mark and make the {style} answer it.","Re-open an earlier decision instead of moving on."),
            "CONTRADICT":(f"The dominant rhythm is becoming predictable. Cut across it with a {style}.","Oppose the current direction before it becomes too obedient."),
            "CONNECT":(f"Bridge two separated structures with a {style}.","Pull distant zones into the same argument."),
            "ESCAPE":(f"This area is overloaded. Move the {style} toward open space.","Leave the crowded center and recover some air."),
            "RESOLVE":(f"Use one controlled {style} to tighten the ending.","Reduce the remaining uncertainty without flattening the drawing."),
        }
        if transform=="none" and not erase and relation not in ("avoid_overcrowding","develop_secondary_branch") and self.rng.random()<.42:return self.rng.choice(strategic.get(strategy,strategic["BUILD"]))
        if erase:return self.rng.choice(("This knot is too heavy. Cut a breath through it.","The field is choking here. Remove a narrow channel.","Erase part of the collision so the edges can speak."))
        if relation=="avoid_overcrowding":return self.rng.choice((f"Too much weight nearby. Send a {style} toward open ground.",f"This patch is saturated. Break away with a {style}.",f"Crowding detected. Let the {style} escape the cluster."))
        if transform!="none":
            transformations={"repeat":"Repeat the remembered gesture without obeying it exactly.","distort":"Warp the remembered gesture until it becomes unfamiliar.","loose_mirror":"Reflect the old movement through an imperfect axis.","extend":"Keep the earlier motion alive past its old boundary.","interrupt":"Interrupt the remembered form with a hostile crossing.","cross":"Drive through the previous mark and make the collision visible.","shrink":"Compress the remembered movement into a tighter signal.","enlarge":"Inflate the remembered movement until it dominates the field."}
            return transformations.get(transform,f"Transform the remembered {style}.")
        if relation=="revisit_and_develop":return self.rng.choice((f"The earlier structure is pulling me back. Complicate it with a {style}.",f"Return to the charged area and fold a {style} through it.",f"Re-enter this memory; make the {style} less obedient."))
        if relation=="develop_secondary_branch":return self.rng.choice(("Fork the structure again before it settles.","Split this branch and make it argue with its source.","Grow a second direction out of the same wound."))
        if layer=="PRIMARY":return self.rng.choice((f"Establish {style} motion as an unstable spine.",f"Throw a {style} across the empty field.",f"Use a {style} to disturb the first balance."))
        if layer=="SECONDARY":return self.rng.choice((f"Counter the main structure with a {style}.",f"Build pressure beside the focal mass with a {style}.",f"Add a {style} that refuses the dominant direction."))
        return self.rng.choice((f"Sharpen the edge with a small {style}.",f"Leave a {style} where the rhythm weakens.",f"Complicate the resolution with one last {style}."))

    def choose_brush_technique(self,phase,style,relation,transform,o,erase,motif):
        """Choose the physical tool from the fly's current artistic intent and observed canvas."""
        if erase:return "subtractive","selective_erasure"
        plan_pass=(self.current_plan or {}).get("pass","")
        if plan_pass=="BLOCK_IN":return "dry_brush","overpainting"
        if plan_pass=="PRIMARY_FORMS":return ("dry_brush","overpainting") if style in ("bold","sweep","branch","web") else ("ink_line","continuous")
        if plan_pass=="SECONDARY_RHYTHMS":
            if style in ("segmented","lattice"):return "fine_pen","cross_hatching"
            if style in ("cluster","starburst"):return "stipple","stippling"
            return ("soft_paint","layered_glazing") if style in ("loop","spiral","orbit","coil","petal") else ("fine_pen","hatching")
        if plan_pass=="INTERRUPT":
            if style in ("cluster","starburst"):return "splatter","stippling"
            return "charcoal_grain","smudged_dragging"
        if plan_pass=="RETURN":return ("fine_pen","hatching") if style in ("contour","echo","hook") else ("soft_paint","layered_glazing")
        if plan_pass=="EDIT":
            if style in ("segmented","lattice","cross"):return "fine_pen","cross_hatching"
            return "fine_pen","hatching"
        if plan_pass=="RESOLVE":return "fine_pen","continuous"
        if style in ("cluster","starburst"):return ("splatter","stippling") if phase in ("CONTRAST","DEVELOPMENT") else ("stipple","stippling")
        if style in ("segmented","lattice"):return ("fine_pen","cross_hatching") if float(o.get("localDensity",0))>.5 else ("ink_line","hatching")
        if style in ("jitter","fracture"):return "charcoal_grain","smudged_dragging"
        if style in ("bold","web"):return ("dry_brush","overpainting") if phase=="STRUCTURE" else ("charcoal_grain","cross_hatching")
        if style in ("loop","spiral","coil","orbit","petal"):return ("soft_paint","layered_glazing") if phase in ("DEVELOPMENT","REFINEMENT") else ("ink_line","continuous")
        if phase=="EXPLORATION":tool,technique="ink_line","continuous"
        elif phase=="STRUCTURE":tool,technique="dry_brush","overpainting"
        elif phase=="DEVELOPMENT":tool,technique="soft_paint","layered_glazing"
        elif phase=="CONTRAST":tool,technique="charcoal_grain","smudged_dragging"
        elif phase=="REFINEMENT":tool,technique="fine_pen","hatching"
        else:tool,technique="wash","layered_glazing"
        if motif and transform in ("repeat","loose_mirror","shrink","enlarge"):
            previous=motif.get("brushTool")
            alternatives=[candidate for candidate in ("fine_pen","dry_brush","wash","stipple","soft_paint") if candidate!=previous]
            tool=alternatives[(self.decision_count+len(style))%len(alternatives)];technique="motif_repetition_different_brush"
        return tool,technique

    def decide(self,request,limits):
        o=request.observation;hard=self.hard_limit(o,limits)
        if hard:return self.finish(o,limits,hard)
        self.remember_result(o)
        maturity_gate=.9+self.complexity*.1
        if self.decision_count>=max(30,round(self.desired_decisions*maturity_gate)):
            ev=self.evaluate(o,limits);enough_families=len(self.style_counts)>=max(4,self.target_families-2)
            if enough_families and ev.get("finishReady") and ev["readiness"]>=.76 and (self.decision_count>=self.desired_decisions or int(o.get("consecutiveLowChange",0))>=5 or self.rng.random()<.025):return self.finish(o,limits)
        self.decision_count+=1;phase=self.phase();evaluation=None;phase_changed=phase!=self.phase_previous
        if phase_changed:self.phase_previous=phase;self.gesture_remaining=0
        if self.decision_count>=self.next_evaluation:
            evaluation=self.evaluate(o,limits);self.next_evaluation+=self.rng.randint(6,10)
            if evaluation["repetition"]>.5 or evaluation["directionVariety"]<.42 or self.rng.random()<self.mutation:self.tendency=self.rng.choice([s for s in PHASE_STYLES[phase] if s!=self.tendency])
        self.current_plan=self.director.plan(
            phase,o,self.decision_count,
            force=phase_changed,
            style_counts=self.style_counts,
            intersections=int(o.get("intersections",0) or 0),
            motif_count=len(self.motifs),
        )
        self.subgoal_hold-=1
        if self.subgoal_hold<=0 or self.boredom>.78:
            previous_subgoal=self.subgoal;self.subgoal=self.rng.choice([g for g in SUBGOALS if g!=previous_subgoal]);self.subgoal_hold=self.rng.randint(24,48)
            if self.subgoal=="BUILD_WEIRD_SCENE":self.scene_relation=self.rng.choice(SCENE_RELATIONS[1:]);self.scene_anchor=self.rng.choice(self.zone_anchors);self.scene_partner=self.rng.choice(self.zone_anchors)
        self.update_autonomy(phase,o,evaluation)
        self.strategy_hold-=1
        if phase_changed or evaluation is not None or self.strategy_hold<=0:
            previous=self.strategy;self.strategy=self.choose_strategy(phase,o);self.strategy_hold=self.rng.randint(8,18)
            if self.strategy!=previous:self.strategy_history.append({"decision":self.decision_count,"from":previous,"to":self.strategy,"phase":phase})
        pos=point(o.get("currentForelegPosition"),[735,48]);empty=point(o.get("negativeSpace"),[400,250]);focal=point(o.get("focalArea"),self.primary_anchor);visited=o.get("visitedAreas",[]) or []
        if self.relocation_target:
            action=self.relocation_action(self.relocation_target,phase,pos,evaluation);self.last_observation=json.loads(json.dumps(o));return action
        if self.gesture_remaining<=0 and (phase_changed or self.rng.random()<.32):
            target=self.choose_zone(phase,o);distance=math.dist(pos,target)
            if distance>88:
                self.relocation_target=target;action=self.relocation_action(target,phase,pos,evaluation);self.last_observation=json.loads(json.dumps(o));return action
            self.gesture_remaining=self.rng.randint(12,22)
        layer="PRIMARY" if phase in ("EXPLORATION","STRUCTURE") else "SECONDARY" if phase in ("DEVELOPMENT","CONTRAST") else "TERTIARY"
        style=self.choose_style(phase,o);motif=None;transform="none"
        motif_chance=(.28+self.complexity*.58)*(1 if phase in ("DEVELOPMENT","REFINEMENT","RESOLUTION") else .62)
        if self.rng.random()<motif_chance:
            motif=self.choose_motif()
            if motif:
                plan_transforms=self.current_plan.get("transform_pool",()) if self.current_plan else ()
                transform=self.rng.choice(plan_transforms) if plan_transforms and self.rng.random()<.7 else self.rng.choice(STRATEGY_TRANSFORMS.get(self.strategy,TRANSFORMS));style=motif["style"] if transform in ("repeat","loose_mirror","shrink","enlarge") else "cross" if transform in ("interrupt","cross") else self.rng.choice(PHASE_STYLES[phase])
        if self.branch_cooldown>0:
            self.branch_cooldown-=1
            if style=="branch":style=self.rng.choice([family for family in PHASE_STYLES[phase] if family!="branch"])
        overcrowded=int(o.get("nearbyLines",0))>4 or float(o.get("localDensity",0))>.7
        seek_empty=self.strategy=="ESCAPE" or ((overcrowded or int(o.get("physicalActionCount",0))%11==0) and self.rng.random()<self.personality["crowdAvoidance"])
        if self.branch_remaining>0 and self.branch_anchor:
            target=self.branch_anchor;self.branch_index+=1;self.branch_remaining-=1;branch_angle=(self.branch_index-(self.branch_index//2))*(((-1)**self.branch_index)*(.38+self.complexity*.34));heading=math.atan2(target[1]-pos[1],target[0]-pos[0])+branch_angle;style="branch";relation="develop_secondary_branch";layer="SECONDARY";transform="extend"
            if self.branch_remaining==0:self.branch_cooldown=self.rng.randint(4,7)
        else:
            revisit=bool(visited) and (self.strategy=="REVISIT" or self.rng.random()<self.personality["returnBias"])
            directed=point(self.current_plan.get("target_point"),focal) if self.current_plan else focal
            use_directed=bool(self.current_plan) and self.rng.random()<.82 and not motif and not seek_empty
            target=empty if seek_empty else point(motif["point"],focal) if motif else directed if use_directed else point(self.rng.choice(visited),focal) if revisit else self.primary_anchor if layer=="PRIMARY" else focal
            heading=math.atan2(target[1]-pos[1],target[0]-pos[0]);relation="avoid_overcrowding" if seek_empty else f"motif_{transform}" if motif else "director_region_build" if use_directed else "revisit_and_develop" if revisit else "build_primary_structure" if layer=="PRIMARY" else "support_existing_structure"
        dominant=float(o.get("dominantDirection",self.heading));uniform=float(o.get("directionalUniformity",0))
        if style in ("cross","segmented") and uniform>.42:heading=dominant+math.pi/2+self.rng.uniform(-.25,.25)
        elif transform=="loose_mirror" and motif:heading=math.pi-motif["heading"]+self.rng.uniform(-.24,.24)
        elif transform=="repeat" and motif:heading=motif["heading"]+self.rng.uniform(-.12,.12)
        elif transform=="interrupt" and motif:heading=motif["heading"]+math.pi/2+self.rng.uniform(-.2,.2)
        self.heading+=angle_delta(self.heading,heading)*(.28+self.personality["order"]*.42)+self.rng.uniform(-.48,.48)*self.personality["chaos"]
        scale=.35+self.rng.random()*(.65+self.complexity*1.25)
        if transform=="shrink":scale=(motif or {}).get("scale",1)*.55
        if transform=="enlarge":scale=(motif or {}).get("scale",1)*1.5
        if style in ("accent","jitter","cluster","hook"):scale*=.62
        if style in ("sweep","bold","orbit","web","lattice","starburst"):scale*=1.32
        if self.motif_theme in FIGURATIVE_MOTIFS and self.motif_intrusion:scale=max(scale,1.05)
        if self.subgoal=="MAKE_BIG_ICON":scale*=1.42
        elif self.subgoal=="MAKE_SMALL_SWARM":scale*=.68
        elif self.readability_mode=="LITERAL" and self.motif_theme in FIGURATIVE_MOTIFS:scale*=1.24
        elif self.readability_mode=="HIDDEN" and self.motif_theme in FIGURATIVE_MOTIFS:scale*=.64
        if self.goal=="AMPLIFY":scale*=1.25
        elif self.goal=="CALM":scale*=.72
        elif self.goal=="JOKE" and self.motif_intrusion:scale*=1.18
        elif self.goal=="SABOTAGE" and self.rng.random()<.4:scale*=1.35
        if self.current_plan:scale*=float(self.current_plan.get("scale_multiplier",1))
        dialect_scale={"MICROGRAPHIC":.58,"MONUMENTAL":1.38,"BROKEN":.76,"ELASTIC":1.12,"ORBITAL":1.08,"ANGULAR":.96,"SCRATCHED":.72}.get(self.stroke_dialect,1)
        scale*=dialect_scale
        scale=clamp(scale,.2,2.35);base=30+50*self.complexity+self.rng.random()*70;movement=clamp(base*scale,12,235)
        if self.stroke_dialect=="MONUMENTAL":movement=clamp(movement*1.24,18,235)
        elif self.stroke_dialect=="MICROGRAPHIC":movement=clamp(movement*.68,10,135)
        elif self.stroke_dialect=="BROKEN":movement=clamp(movement*.76,10,165)
        if self.motif_theme in FIGURATIVE_MOTIFS and self.motif_intrusion:movement=max(movement,self.rng.uniform(85,155))
        if self.subgoal=="MAKE_BIG_ICON":movement=max(movement,self.rng.uniform(125,185))
        elif self.subgoal=="MAKE_SMALL_SWARM":movement=min(movement,self.rng.uniform(55,105))
        curvature={"loop":3.9,"spiral":3.25,"curl":1.7,"sweep":.58,"branch":self.rng.choice((-1.25,1.25)),"cross":.35,"contour":.9,"accent":.22,"bold":.45,"segmented":self.rng.choice((-.85,.85)),"knot":self.rng.choice((-2.7,2.7)),"fracture":self.rng.choice((-1.8,1.8)),"orbit":self.rng.choice((-3.5,3.5)),"web":self.rng.choice((-1.4,1.4)),"coil":self.rng.choice((-3.8,3.8)),"petal":self.rng.choice((-2.2,2.2)),"lattice":self.rng.choice((-1.1,1.1)),"hook":self.rng.choice((-3.1,3.1)),"starburst":self.rng.choice((-2.5,2.5)),"wave":self.rng.choice((-1.7,1.7)),"zigzag":self.rng.choice((-1.1,1.1)),"ribbon":self.rng.choice((-2.4,2.4)),"vortex":self.rng.choice((-3.9,3.9)),"rosette":self.rng.choice((-3.2,3.2)),"maze":self.rng.choice((-.9,.9)),"meander":self.rng.choice((-1.6,1.6)),"blob":self.rng.choice((-2.7,2.7)),"fan":self.rng.choice((-.5,.5)),"helix":self.rng.choice((-3.5,3.5)),"scallop":self.rng.choice((-2.1,2.1)),"scribble":self.rng.choice((-3.8,3.8))}.get(style,self.rng.uniform(-.55,.55))
        if self.stroke_dialect=="ANGULAR":curvature=clamp(curvature*.46+self.rng.uniform(-.28,.28),-4,4)
        elif self.stroke_dialect=="ELASTIC":curvature=clamp(curvature*1.35+self.rng.uniform(-.35,.35),-4,4)
        elif self.stroke_dialect=="ORBITAL":curvature=clamp(curvature*1.48+self.rng.choice((-1,1))*.32,-4,4)
        elif self.stroke_dialect=="BROKEN":curvature=clamp(curvature*.72+self.rng.uniform(-1.1,1.1),-4,4)
        elif self.stroke_dialect=="SCRATCHED":curvature=clamp(curvature+self.rng.uniform(-1.45,1.45),-4,4)
        if transform=="distort":curvature=clamp(curvature*self.rng.uniform(-1.7,1.7),-4,4)
        plan_pass=(self.current_plan or {}).get("pass","")
        edit_zone=plan_pass=="EDIT" and float(o.get("localDensity",0))>.32
        erase=edit_zone and self.rng.random()<self.personality.get("editBias",.5)*.34
        brush=self.rng.random()>(.008+(.035 if seek_empty else 0));pressure=clamp((.78+self.rng.random()*.22) if style in ("bold","web") else (.08+self.rng.random()*.25) if style=="accent" else .14+self.rng.random()*.86,.06,1)
        depth=round(1+self.complexity*3) if style=="branch" else 0
        if style=="branch" and not self.branch_remaining and self.branch_cooldown==0 and self.rng.random()<.3+self.complexity*.3:self.branch_anchor=pos[:];self.branch_remaining=max(1,depth-1);self.branch_index=0
        character="bold_structural" if style in ("bold","web") else "delicate_accent" if style=="accent" else "scratch" if style in ("jitter","fracture") else "layered"
        brush_tool,technique=self.choose_brush_technique(phase,style,relation,transform,o,erase,motif)
        public_reason=self.public_reason(phase,layer,style,relation,transform,o,erase,self.strategy)
        plan=self.current_plan or {}
        tempo_multiplier={"TWITCHY":.62,"SMOOTH":.92,"INTERRUPTED":1.18,"RITUALISTIC":1.42}[self.tempo_mode]
        profile_multiplier={"QUICK":.82,"STANDARD":1.0,"LONG":1.08,"OBSESSIVE":1.14}[self.duration_profile]
        action_duration=round((180+movement*(3.2-self.rng.random()*.7))*tempo_multiplier*profile_multiplier)
        hesitation_base=(70 if phase in ("REFINEMENT","RESOLUTION") else 42)*tempo_multiplier
        action=BrainAction(intent="MOVE",targetDirection=round(self.heading,3),movementDistance=round(movement,3),curvature=round(curvature,3),speed=round(.42+self.rng.random()*.38,3),duration=action_duration,brushDown=brush,pressure=round(pressure,3),hesitation=round(12+self.rng.random()*hesitation_base),exploration=.92 if seek_empty else round(.18+self.rng.random()*.64,3),attentionTarget={"kind":"negative_space" if seek_empty else "motif" if motif else "director_region" if relation=="director_region_build" else "structural_anchor","point":[round(v,3) for v in target]},eraseIntent=erase,movementStyle=style,relationshipToExistingMarks="selective_erase" if erase else relation,motifReference={k:motif[k] for k in ("decision","style","point","scale","brushTool","technique") if k in motif} if motif else None,color=self.choose_color(phase),confidence=round(.58+self.rng.random()*.4,3),reason=public_reason,phase=phase,evaluation=evaluation,scale=round(scale,3),layerRole=layer,motifTransform=transform,branchingDepth=depth,strokeCharacter=character,brushTool=brush_tool,technique=technique,motifHint=self.motif_theme,autonomyGoal=self.goal,paletteName=self.palette_name,compositionMode=self.composition_mode,subgoal=self.subgoal,sceneRelation=self.scene_relation,compositionPass=plan.get("pass","SCOUT_MAP"),regionTarget=int(plan.get("target_region",-1)),macroIntent=plan.get("macro_intent",""),subjectProgram=self.subject_program_name)
        self.style_counts[style]=self.style_counts.get(style,0)+1;self.tendency=style;self.gesture_remaining=max(0,self.gesture_remaining-1)
        self.motifs.append({"decision":self.decision_count,"style":style,"point":pos[:],"heading":self.heading,"scale":scale,"curvature":curvature,"brushTool":brush_tool,"technique":technique,"interest":.45+self.rng.random()*.45});self.motifs=self.motifs[-48:];self.last_observation=json.loads(json.dumps(o));return action

COMPLEX_ART_VERSION="JPGFLY-COMPLEX-ART/1.0"
COMPLEX_ART_STAGES=(
    ("MAP_FIELD",.00,.12,"map the dominant axis and protect one quiet region"),
    ("BUILD_PRIMARY",.12,.31,"build two or three large load-bearing forms"),
    ("WEAVE_SECONDARY",.31,.56,"repeat and transform motifs across separated regions"),
    ("INTERRUPT_CONTRAST",.56,.73,"break predictable rhythm with counter-direction and material contrast"),
    ("RETURN_EDIT",.73,.89,"revisit earlier forms, edit collisions, deepen hierarchy"),
    ("RESOLVE",.89,1.01,"reduce noise without flattening tension"),
)
COMPLEX_ART_STAGE_STYLES={
    "MAP_FIELD":("sweep","contour","branch"),
    "BUILD_PRIMARY":("bold","web","branch","lattice"),
    "WEAVE_SECONDARY":("echo","orbit","contour","coil","petal"),
    "INTERRUPT_CONTRAST":("cross","fracture","segmented","starburst"),
    "RETURN_EDIT":("contour","echo","hook","wave"),
    "RESOLVE":("contour","accent","echo","hook"),
}
COMPLEX_ART_MATERIALS={
    "ANGULAR":("dry_brush","fine_pen","charcoal_grain"),
    "ELASTIC":("soft_paint","wash","ink_line"),
    "MICROGRAPHIC":("fine_pen","stipple","ink_line"),
    "MONUMENTAL":("dry_brush","charcoal_grain","wash"),
    "BROKEN":("charcoal_grain","dry_brush","fine_pen"),
    "ORBITAL":("soft_paint","ink_line","wash"),
    "SCRATCHED":("charcoal_grain","fine_pen","dry_brush"),
}
COMPLEX_ART_DOODLY={"scribble","jitter","blob","cluster"}

def complex_art_enabled():
    return os.environ.get("JPGFLY_COMPLEX_ART_ENABLED","true").lower() not in ("0","false","off","no")

class ComplexArtController:
    """Session-level art direction and telemetry critic for the Qwen painter."""
    def __init__(self,fallback):
        subject=list(getattr(fallback,"subject_program",()) or ())
        defaults=["MASK","BONE","EYEBALL","WING","GRID"]
        while len(subject)<5:subject.append(defaults[len(subject)])
        self.primary=tuple(dict.fromkeys(subject[:2]))
        self.secondary=tuple(x for x in dict.fromkeys(subject[2:6]) if x not in self.primary) or ("MASK","BONE")
        self.spatial=str(getattr(fallback,"spatial_program","SCATTERED_ISLANDS"))
        self.composition=str(getattr(fallback,"composition_mode","SWARM"))
        self.archetype=str(getattr(fallback,"archetype","TENSION_FIELD"))
        dialect=str(getattr(fallback,"stroke_dialect","ANGULAR"))
        self.materials=COMPLEX_ART_MATERIALS.get(dialect,("ink_line","charcoal_grain","dry_brush"))
        desired=int(getattr(fallback,"desired_decisions",520) or 520)
        lo=int(os.environ.get("JPGFLY_COMPLEX_ART_TARGET_MIN","140"));hi=int(os.environ.get("JPGFLY_COMPLEX_ART_TARGET_MAX","220"))
        self.target=max(120,min(hi,max(lo,desired)))
        density=float(getattr(fallback,"density",.64) or .64);self.density_target=clamp(.28+density*.34,.34,.62)
        self.palette=str(getattr(fallback,"palette_name","UNKNOWN"))
        self.thesis=(f"Build one coherent {self.spatial.lower().replace('_',' ')} structure using "
                     f"{self.composition.lower().replace('_',' ')} composition and {self.archetype.lower().replace('_',' ')} logic. "
                     "Repeat motifs with deliberate changes of scale, material, direction and density.")
        from collections import Counter,deque
        self.actions=0;self.motifs=Counter();self.brushes=Counter();self.styles=Counter();self.passes=Counter();self.scales=Counter()
        self.recent_brushes=deque(maxlen=8);self.recent_styles=deque(maxlen=10);self.recent_motifs=deque(maxlen=12);self.last_critique={}

    def stage(self,n):
        progress=clamp(n/max(1,self.target),0,1)
        for name,lo,hi,goal in COMPLEX_ART_STAGES:
            if lo<=progress<hi:return name,goal,progress
        return COMPLEX_ART_STAGES[-1][0],COMPLEX_ART_STAGES[-1][3],progress

    @staticmethod
    def band(scale):return "micro" if scale<.7 else "macro" if scale>=1.3 else "mid"

    def critique(self,o,n):
        occupancy=clamp(float(o.get("canvasOccupancy",0) or 0),0,1);direction=1-clamp(float(o.get("directionalUniformity",.5) or .5),0,1)
        contrast=clamp(float(o.get("densityContrast",0) or 0),0,1);repetition=clamp(float(o.get("repetition",0) or 0),0,1);meaningful=clamp(float(o.get("meaningfulChangeRate",.7) or .7),0,1)
        occ_fit=1-min(1,abs(occupancy-self.density_target)/max(.18,self.density_target));motif_var=min(1,len([k for k in self.motifs if k!="NONE"])/3);brush_var=min(1,len(self.brushes)/4);scale_var=min(1,len(self.scales)/3)
        score=clamp(occ_fit*.22+direction*.16+contrast*.15+meaningful*.14+motif_var*.12+brush_var*.10+scale_var*.11-max(0,repetition-.55)*.18,0,1)
        needs=[]
        if occupancy<self.density_target*.62:needs.append("build larger connected primary masses")
        if direction<.38:needs.append("add a clear counter-direction")
        if contrast<.14 and n>80:needs.append("increase dense-versus-quiet contrast")
        if repetition>.58:needs.append("transform or interrupt the repeated rhythm")
        if brush_var<.5 and n>70:needs.append("change material family")
        if scale_var<.67 and n>80:needs.append("increase macro/micro scale contrast")
        if motif_var<.67 and n>100:needs.append("develop a secondary motif")
        if not needs:needs.append("deepen the existing structure; do not add unrelated icons")
        stage,_,progress=self.stage(n)
        allowed=progress>=.88 and score>=float(os.environ.get("JPGFLY_COMPLEX_ART_MIN_SCORE",".60")) and occupancy>=.22 and len(self.brushes)>=3 and len(self.scales)>=2 and repetition<=.74
        self.last_critique={"score":round(score,3),"stage":stage,"progress":round(progress,3),"finish_allowed":allowed,"needs":needs[:3]};return self.last_critique

    def prompt_fragment(self,o,n):
        stage,goal,progress=self.stage(n);critic=self.critique(o,n)
        payload={"mode":"COMPLEX_ART","thesis":self.thesis,"stage":stage,"goal":goal,"progress":round(progress,3),"primary":self.primary,"secondary":self.secondary,"materials":self.materials,"palette":self.palette,"history":{"moves":self.actions,"motifs":self.motifs.most_common(5),"brushes":self.brushes.most_common(5),"scales":dict(self.scales)},"critic":critic,"rules":["build one coherent artwork, not unrelated doodles","connect or echo isolated icons later","revisit and transform earlier motifs","use macro/micro scale contrast","preserve at least one quiet negative-space region","scribble/jitter/blob may interrupt but cannot dominate"]}
        return " COMPLEX ART MODE is authoritative. Follow this session plan: "+json.dumps(payload,separators=(",",":"))

    def least_style(self,stage):return min(COMPLEX_ART_STAGE_STYLES.get(stage,("contour","branch")),key=lambda x:self.styles.get(x,0))
    def least_motif(self):
        pool=self.primary+self.secondary
        return min(pool,key=lambda x:self.motifs.get(x,0)) if pool else "MASK"

    def continue_action(self,a,o,n):
        stage,_,_=self.stage(n);pos=o.get("currentForelegPosition") or [400,250];target=(o.get("negativeSpace") if stage in ("RETURN_EDIT","RESOLVE") else o.get("focalArea")) or [400,250]
        try:a.targetDirection=math.atan2(float(target[1])-float(pos[1]),float(target[0])-float(pos[0]))
        except (TypeError,ValueError,IndexError):pass
        a.intent="MOVE";a.movementDistance=64.;a.brushDown=True;a.speed=.54;a.duration=360;a.pressure=.55;a.hesitation=42;a.exploration=.42;a.eraseIntent=False
        a.movementStyle=self.least_style(stage);a.relationshipToExistingMarks="complex_art_continue_unresolved_structure";a.motifHint=self.least_motif()
        a.scale=1.45 if "macro" not in self.scales else .58 if "micro" not in self.scales else 1.;a.reason="The composition is not structurally resolved yet; continue the existing room.";return a

    def normalize_action(self,a,o,limits,n):
        del limits
        critic=self.critique(o,n);stage,goal,_=self.stage(n);intent=str(getattr(a,"intent","") or "").upper()
        if ("FINISH" in intent or intent in ("DONE","STOP","END","COMPLETE")) and not critic["finish_allowed"]:a=self.continue_action(a,o,n)
        # Never let the Qwen painter spend an empty room only moving its tip.
        # Preserve deliberate repositioning later, but force visible marks while the
        # canvas is empty or after repeated no-change actions.
        try:occupancy=clamp(float(o.get("canvasOccupancy",0) or 0),0,1)
        except (TypeError,ValueError):occupancy=0
        try:low_change=int(o.get("consecutiveLowChange",0) or 0)
        except (TypeError,ValueError):low_change=0
        if intent not in ("FINISH","DONE","STOP","END","COMPLETE","FINISH_ARTWORK","COMPLETE_ARTWORK","END_ARTWORK") and ((n<12 and occupancy<.025) or low_change>=3):
            a.brushDown=True;a.eraseIntent=False
            try:a.movementDistance=max(42.,float(a.movementDistance))
            except (TypeError,ValueError):a.movementDistance=42.
            try:a.pressure=max(.38,float(a.pressure))
            except (TypeError,ValueError):a.pressure=.5
            relation=str(getattr(a,"relationshipToExistingMarks","") or "")
            if "visible_mark_guard" not in relation:a.relationshipToExistingMarks=(relation+" | visible_mark_guard").strip(" |")
        a.compositionPass=stage;a.macroIntent=f"{stage}:{goal}"
        a.layerRole="PRIMARY" if stage in ("MAP_FIELD","BUILD_PRIMARY") else "SECONDARY" if stage in ("WEAVE_SECONDARY","INTERRUPT_CONTRAST") else "TERTIARY"
        style=str(getattr(a,"movementStyle","") or "")
        if style in COMPLEX_ART_DOODLY and sum(x in COMPLEX_ART_DOODLY for x in self.recent_styles)>=4:a.movementStyle=self.least_style(stage);a.relationshipToExistingMarks="complex_art_restore_structural_hierarchy"
        brush=str(getattr(a,"brushTool","") or "")
        if brush and len(self.recent_brushes)>=6 and all(x==brush for x in list(self.recent_brushes)[-6:]):
            alt=next((x for x in self.materials if x!=brush),None)
            if alt:a.brushTool=alt;a.technique="motif_repetition_different_brush"
        motif=str(getattr(a,"motifHint","") or "")
        if (not motif or motif=="NONE") and stage not in ("MAP_FIELD","RESOLVE") and self.actions%5==0:a.motifHint=self.least_motif()
        elif motif!="NONE" and len(self.recent_motifs)>=9 and all(x==motif for x in list(self.recent_motifs)[-9:]):a.motifHint=self.least_motif();a.motifTransform="distort"
        try:scale=float(getattr(a,"scale",1) or 1)
        except (TypeError,ValueError):scale=1
        if self.actions>24 and len(self.scales)<2:
            if "macro" not in self.scales:a.scale=max(1.45,scale)
            elif "micro" not in self.scales:a.scale=min(.62,scale)
        return a

    def record_action(self,a):
        if str(getattr(a,"intent","") or "").upper()!="MOVE":return
        self.actions+=1;motif=str(getattr(a,"motifHint","") or "NONE");brush=str(getattr(a,"brushTool","") or "unknown");style=str(getattr(a,"movementStyle","") or "unknown");stage=str(getattr(a,"compositionPass","") or "unknown")
        try:scale=float(getattr(a,"scale",1) or 1)
        except (TypeError,ValueError):scale=1
        for counter,key in ((self.motifs,motif),(self.brushes,brush),(self.styles,style),(self.passes,stage),(self.scales,self.band(scale))):counter[key]+=1
        self.recent_motifs.append(motif);self.recent_brushes.append(brush);self.recent_styles.append(style)

    def snapshot(self):
        return {"complex_art":True,"version":COMPLEX_ART_VERSION,"visual_thesis":self.thesis,"spatial_program":self.spatial,"composition_mode":self.composition,"archetype":self.archetype,"primary_motifs":list(self.primary),"secondary_motifs":list(self.secondary),"material_priority":list(self.materials),"palette":self.palette,"target_decisions":self.target,"action_count":self.actions,"motif_counts":dict(self.motifs.most_common(12)),"brush_counts":dict(self.brushes.most_common(10)),"style_counts":dict(self.styles.most_common(12)),"pass_counts":dict(self.passes),"scale_bands":dict(self.scales),"last_critique":self.last_critique}

class BrainUnavailable(RuntimeError):
    """The configured painting brain cannot answer right now."""

class OllamaFlyBrain:
    mode="QWEN VISUAL BRAIN · ONLINE"
    def __init__(self,fallback):
        self.fallback=fallback
        self.url=os.environ.get("JPGFLY_OLLAMA_URL","http://127.0.0.1:11434").rstrip("/")
        configured_malecns=os.environ.get("JPGFLY_MALECNS_URL","").strip().rstrip("/")
        if configured_malecns:
            self.malecns_url=configured_malecns
        elif self.url.endswith("/ollama"):
            self.malecns_url=self.url[:-7]+"/malecns"
        else:
            self.malecns_url="http://127.0.0.1:4690"
        self.malecns_timeout=max(2,min(30,int(os.environ.get("JPGFLY_MALECNS_TIMEOUT","12"))))
        self.malecns_strength=clamp(float(os.environ.get("JPGFLY_MALECNS_STRENGTH",".22")),0,.55)
        self.last_malecns_bias={}
        self.model=os.environ.get("JPGFLY_OLLAMA_MODEL","qwen3:8b").strip() or "qwen3:8b"
        self.timeout=max(8,min(120,int(os.environ.get("JPGFLY_OLLAMA_BRAIN_TIMEOUT","60"))))
        self.retry_seconds=max(2,min(300,int(os.environ.get("JPGFLY_OLLAMA_RETRY_SECONDS","3"))))
        self.retry_at=0.0
        self.complex_art=ComplexArtController(fallback) if complex_art_enabled() else None
        if self.complex_art:self.mode="QWEN VISUAL BRAIN · COMPLEX ART"
        if not self.model:
            raise RuntimeError("model required")

    def _dumb_dumb(self,request,limits):
        self.mode="DUMB DUMB MODE · PURE FLY INSTINCT"
        return self.fallback.decide(request,limits)

    def context_snapshot(self):
        return self.complex_art.snapshot() if self.complex_art else {}

    def _malecns_bias(self,observation,action):
        try:
            focus=observation.get("focalArea") or observation.get("currentForelegPosition") or [400,250]
            if isinstance(focus,dict):
                focus=focus.get("point") or focus.get("center") or [400,250]
            try:
                fx=clamp(float(focus[0])/800.,0,1)
                fy=clamp(float(focus[1])/500.,0,1)
            except (TypeError,ValueError,IndexError):
                fx=.5;fy=.5
            recent=observation.get("recentMarks") or []
            payload={
                "canvasOccupancy":float(observation.get("canvasOccupancy",.25) or .25),
                "densityContrast":float(observation.get("densityContrast",.35) or .35),
                "memoryStrength":clamp(len(recent)/24.,0,1),
                "novelty":float(getattr(action,"exploration",.5) or .5),
                "focusX":fx,
                "focusY":fy,
                "focusScale":clamp(float(getattr(action,"scale",1) or 1)/2.5,.08,1),
                "phase":str(getattr(action,"compositionPass","") or getattr(action,"phase","OBSERVE")),
                "durationMs":20,
            }
            headers={"content-type":"application/json"}
            token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
            if token:
                headers["authorization"]="Bearer "+token
            req=urllib.request.Request(
                self.malecns_url+"/stimulate",
                data=json.dumps(payload,separators=(",",":")).encode(),
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req,timeout=self.malecns_timeout) as response:
                result=json.load(response)
            bias=result.get("bias") or {}
            if not isinstance(bias,dict):
                return {}
            self.last_malecns_bias=bias
            return bias
        except Exception as exc:
            LOGGER.warning("MaleCNS bias unavailable: %s: %s",type(exc).__name__,str(exc)[:180])
            self.last_malecns_bias={}
            return {}

    def _apply_malecns_bias(self,action,bias):
        if not bias or self.malecns_strength<=0:
            return action
        strength=self.malecns_strength
        try:
            action.targetDirection=float(action.targetDirection)+clamp(float(bias.get("direction_bias",0)),-1,1)*.70*strength
        except (TypeError,ValueError):
            pass
        try:
            action.pressure=clamp((1-strength)*float(action.pressure)+strength*float(bias.get("pressure_bias",action.pressure)),0,1)
        except (TypeError,ValueError):
            pass
        try:
            action.exploration=clamp((1-strength)*float(action.exploration)+strength*float(bias.get("exploration_bias",action.exploration)),0,1)
        except (TypeError,ValueError):
            pass
        try:
            action.scale=clamp((1-strength)*float(action.scale)+strength*float(bias.get("scale_bias",action.scale)),.15,2.5)
        except (TypeError,ValueError):
            pass
        try:
            target_hesitation=clamp(float(bias.get("hesitation_bias",.3)),0,1)*300
            action.hesitation=int(clamp((1-strength)*float(action.hesitation)+strength*target_hesitation,0,1000))
        except (TypeError,ValueError):
            pass
        relation=str(getattr(action,"relationshipToExistingMarks","") or "")
        if "malecns" not in relation.lower():
            action.relationshipToExistingMarks=(relation+" | MaleCNS neural bias").strip(" |")
        return action

    def decide(self,request,limits):
        if time.monotonic()<self.retry_at:
            return self._dumb_dumb(request,limits)

        complex_prompt=self.complex_art.prompt_fragment(request.observation,self.fallback.decision_count) if self.complex_art else ""
        action_schema=BrainAction.model_json_schema()
        prompt=(
            "You are the fly. Return one JSON foreleg action only; never points, paths, or a whole composition. "
            "Use phase, layer, motif transformation, scale and mark family deliberately. "
            "Keep reason and relationship strings very short."
            +complex_prompt+
            " Observation: "+json.dumps(request.observation,separators=(",",":"))
        )
        try:
            headers={"content-type":"application/json"}
            auth_token=os.environ.get("JPGFLY_CONTROL_TOKEN","").strip() or os.environ.get("JPGFLY_OLLAMA_AUTH_TOKEN","").strip()
            if auth_token:
                headers["authorization"]="Bearer "+auth_token
            qwen_started=time.perf_counter()
            req=urllib.request.Request(
                self.url+"/api/generate",
                data=json.dumps({
                    "model":self.model,
                    "prompt":prompt,
                    "stream":False,
                    "format":action_schema,
                    "think":False,
                    "keep_alive":"30m",
                    "options":{"temperature":0.35,"num_predict":480},
                },separators=(",",":")).encode(),
                headers=headers,
            )
            with urllib.request.urlopen(req,timeout=self.timeout) as response:
                result=json.load(response)
            qwen_ms=(time.perf_counter()-qwen_started)*1000
            action=BrainAction.model_validate_json(result["response"])
            intent=str(action.intent or "").strip().upper().replace("-","_").replace(" ","_")
            if intent in ("FINISH","COMPLETE","DONE","STOP","END","FINISH_ARTWORK","COMPLETE_ARTWORK","END_ARTWORK"):
                action.intent="FINISH_ARTWORK"
            else:
                action.intent="MOVE"
            if self.complex_art:
                action=self.complex_art.normalize_action(action,request.observation,limits,self.fallback.decision_count)
                self.complex_art.record_action(action)
            malecns_started=time.perf_counter()
            malecns_bias=self._malecns_bias(request.observation,action)
            malecns_ms=(time.perf_counter()-malecns_started)*1000
            if malecns_bias:
                action=self._apply_malecns_bias(action,malecns_bias)
            LOGGER.info(
                "JPGFLY decision timing qwen_ms=%.1f malecns_ms=%.1f total_model_ms=%.1f",
                qwen_ms,malecns_ms,qwen_ms+malecns_ms,
            )
            self.retry_at=0.0
            self.mode=("QWEN VISUAL BRAIN · COMPLEX ART" if self.complex_art else "QWEN VISUAL BRAIN · ONLINE")+(" · MALECNS" if malecns_bias else "")
            self.fallback.decision_count+=1
            return action
        except urllib.error.HTTPError as exc:
            LOGGER.warning("Qwen visual brain HTTP failure: status=%s url=%s",exc.code,self.url)
            self.retry_at=time.monotonic()+self.retry_seconds
            return self._dumb_dumb(request,limits)
        except Exception as exc:
            LOGGER.warning("Qwen visual brain failure: %s: %s",type(exc).__name__,str(exc)[:240])
            self.retry_at=time.monotonic()+self.retry_seconds
            return self._dumb_dumb(request,limits)

def create_fly_brain(seed,*,complexity=.96,mutation=.42,density=.64,experience=None):
    if experience is None:
        try:
            from experience_memory import visual_bias
            experience=visual_bias()
        except Exception:
            experience={}
    fallback=ProceduralFlyBrain(seed,complexity,mutation,density,experience or {})
    if os.environ.get("JPGFLY_BRAIN_PROVIDER","procedural").lower()=="ollama":
        try:return OllamaFlyBrain(fallback)
        except RuntimeError as exc:raise BrainUnavailable("fly brain is taking a tiny nap") from exc
    return fallback
def configured_brain_mode():return "OLLAMA REQUESTED — VERIFIED PER SESSION" if os.environ.get("JPGFLY_BRAIN_PROVIDER","procedural").lower()=="ollama" else "LOCAL PROCEDURAL FLY BRAIN · STRUCTURED SUBJECT PAINTER"
