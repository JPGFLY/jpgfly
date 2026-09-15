"""Long-horizon compositional director for JPGFLY.

The director does not render pixels. It gives the physical foreleg engine a
painter-like working memory: protected air, primary forms, secondary rhythms,
interruptions, returns, editing, and a stricter resolution gate.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

PHASE_PASS={
    "EXPLORATION":"SCOUT",
    "STRUCTURE":"PRIMARY_FORMS",
    "DEVELOPMENT":"SECONDARY_RHYTHMS",
    "CONTRAST":"INTERRUPT",
    "REFINEMENT":"EDIT",
    "RESOLUTION":"RESOLVE",
}

PASS_STYLES={
    "SCOUT":("sweep","curl","segmented","contour","hook"),
    "BLOCK_IN":("bold","cluster","sweep","contour","lattice"),
    "PRIMARY_FORMS":("bold","branch","lattice","web","cross","starburst","contour"),
    "SECONDARY_RHYTHMS":("echo","loop","spiral","orbit","coil","petal","knot","web"),
    "INTERRUPT":("fracture","cross","jitter","cluster","segmented","starburst"),
    "RETURN":("echo","contour","loop","orbit","hook","branch"),
    "EDIT":("contour","accent","hook","segmented","echo","cross"),
    "RESOLVE":("accent","contour","echo","cross","hook","sweep"),
}

PASS_STRATEGY={
    "SCOUT":"SCOUT",
    "BLOCK_IN":"BUILD",
    "PRIMARY_FORMS":"BUILD",
    "SECONDARY_RHYTHMS":"BUILD",
    "INTERRUPT":"CONTRADICT",
    "RETURN":"REVISIT",
    "EDIT":"REVISIT",
    "RESOLVE":"RESOLVE",
}

PASS_TRANSFORMS={
    "SCOUT":("extend","distort"),
    "BLOCK_IN":("extend","enlarge","repeat"),
    "PRIMARY_FORMS":("extend","repeat","enlarge"),
    "SECONDARY_RHYTHMS":("repeat","loose_mirror","shrink","enlarge"),
    "INTERRUPT":("interrupt","cross","distort"),
    "RETURN":("repeat","loose_mirror","cross","shrink"),
    "EDIT":("shrink","cross","interrupt","repeat"),
    "RESOLVE":("shrink","loose_mirror","repeat"),
}

REGION_CENTERS=tuple(
    (100+200*column,85+165*row)
    for row in range(3)
    for column in range(4)
)


def clamp(value,low,high):
    return max(low,min(high,value))


def _point_region(point):
    try:
        x=float(point[0]);y=float(point[1])
    except (TypeError,ValueError,IndexError):
        return 5
    column=max(0,min(3,int(x/800*4)))
    row=max(0,min(2,int(y/500*3)))
    return row*4+column


@dataclass
class DirectorSnapshot:
    composition_score:float
    regional_spread:float
    density_contrast:float
    protected_space:float
    need:str
    milestone_ratio:float=0.0
    finish_ready:bool=False


class CompositionalDirector:
    """Holds multi-action painting plans above individual brush actions."""

    def __init__(self,seed:int,composition_mode:str,archetype:str,complexity:float,mutation:float,density:float):
        self.seed=int(seed)&0xffffffff
        self.rng=random.Random(self.seed^0xC0A7BEEF)
        self.composition_mode=composition_mode
        self.archetype=archetype
        self.complexity=clamp(float(complexity),.1,1)
        self.mutation=clamp(float(mutation),0,1)
        self.density=clamp(float(density),.1,1)

        self.region_visits=[0]*12
        self.current=None
        self.burst_remaining=0
        self.plan_index=0
        self.last_phase=None
        self.pass_counts={name:0 for name in PASS_STYLES}
        self.plan_history=[]

        self.protected_region=self.rng.randrange(12)
        self.primary_regions=self._choose_primary_regions()
        remaining=[i for i in range(12) if i not in self.primary_regions and i!=self.protected_region]
        self.counter_region=self.rng.choice(remaining or [self.protected_region])

    def _choose_primary_regions(self):
        if self.composition_mode=="CENTRAL_ICON":return [5,6]
        if self.composition_mode=="CORNER_NEST":return [0,1] if self.seed%2==0 else [10,11]
        if self.composition_mode=="TWO_ISLANDS":return [1,10]
        if self.composition_mode=="TOTEM":return [1,5,9]
        if self.composition_mode=="BORDER_CRAWL":return [0,3,8,11]
        if self.composition_mode=="DIAGONAL_ATTACK":return [3,6,9]
        if self.composition_mode=="WEB_FIELD":return [1,5,6,10]
        if self.composition_mode=="PANEL_CHAOS":return [0,2,5,7,9,11]
        if self.composition_mode=="ORBITAL":return [1,2,5,6,9,10]
        return self.rng.sample(range(12),k=3)

    def _densities(self,o):
        raw=o.get("regionDensity") or []
        if len(raw)!=12:return [0.0]*12
        result=[]
        for value in raw:
            try:result.append(clamp(float(value),0,1))
            except (TypeError,ValueError):result.append(0.0)
        return result

    def _visited_regions(self,o):
        counts=[0]*12
        for point in (o.get("visitedAreas") or [])[-48:]:
            counts[_point_region(point)]+=1
        return counts

    def milestones(self):
        completed={
            "scout":self.pass_counts["SCOUT"]>0,
            "block_in":self.pass_counts["BLOCK_IN"]>0 or self.pass_counts["PRIMARY_FORMS"]>0,
            "primary":self.pass_counts["PRIMARY_FORMS"]>0,
            "secondary":self.pass_counts["SECONDARY_RHYTHMS"]>0,
            "interrupt":self.pass_counts["INTERRUPT"]>0,
            "return":self.pass_counts["RETURN"]>0,
            "edit":self.pass_counts["EDIT"]>0,
            "resolve":self.pass_counts["RESOLVE"]>0,
        }
        required=("scout","primary","secondary","interrupt","return","edit")
        ratio=sum(1 for name in required if completed[name])/len(required)
        completed["ratio"]=round(ratio,3)
        completed["finish_ready"]=all(completed[name] for name in required)
        return completed

    def _choose_pass(self,phase,snapshot,decision):
        base=PHASE_PASS.get(phase,"SECONDARY_RHYTHMS")
        if phase=="EXPLORATION":
            return "SCOUT" if self.pass_counts["SCOUT"]<2 else "BLOCK_IN"
        if phase=="STRUCTURE":
            return "PRIMARY_FORMS"
        if phase=="DEVELOPMENT":
            if self.pass_counts["SECONDARY_RHYTHMS"]>=2 and self.pass_counts["RETURN"]==0:
                return "RETURN"
            if snapshot.need=="CONNECT_ISLANDS" and self.pass_counts["RETURN"]<2:
                return "RETURN"
            return "SECONDARY_RHYTHMS"
        if phase=="CONTRAST":
            return "INTERRUPT"
        if phase=="REFINEMENT":
            if self.pass_counts["RETURN"]<2 and decision%3:
                return "RETURN"
            return "EDIT"
        if phase=="RESOLUTION":
            if self.pass_counts["EDIT"]==0:return "EDIT"
            if self.pass_counts["RETURN"]==0:return "RETURN"
            return "RESOLVE"
        return base

    def _score_region(self,index,pass_name,densities,visited,o):
        density=densities[index]
        visits=self.region_visits[index]+visited[index]*.25
        score=self.rng.random()*.05

        if index==self.protected_region:
            score-=1.4 if pass_name not in ("INTERRUPT","RESOLVE") else .35

        if pass_name=="SCOUT":
            score+=(1-density)*1.4-visits*.08
        elif pass_name=="BLOCK_IN":
            score+=(1.0 if index in self.primary_regions else .1)+(1-density)*.42-visits*.03
        elif pass_name=="PRIMARY_FORMS":
            score+=(1.25 if index in self.primary_regions else 0)+(1-density)*.25-visits*.025
        elif pass_name=="SECONDARY_RHYTHMS":
            score+=(.68 if index in self.primary_regions else .2)+(1-abs(density-.5))*.62-visits*.018
        elif pass_name=="INTERRUPT":
            score+=(1.3 if index==self.counter_region else 0)+(1-density)*.35
            if index in self.primary_regions:score-=.28
        elif pass_name=="RETURN":
            score+=(.8 if index in self.primary_regions else .12)+(1-abs(density-.46))*.55
        elif pass_name=="EDIT":
            score+=(.62 if index in self.primary_regions else .18)+(1-abs(density-.4))*.68-visits*.01
        else:
            target=.34+self.density*.16
            score+=(1-abs(density-target))*1.1-visits*.015

        repetition=float(o.get("repetition",0) or 0)
        contrast=float(o.get("densityContrast",0) or 0)
        if repetition>.5 and index not in self.primary_regions:score+=.3
        if contrast<.18 and index==self.counter_region:score+=.32
        return score

    def evaluate(self,o,style_counts=None,intersections=0,motif_count=0):
        densities=self._densities(o)
        active=sum(1 for value in densities if value>.08)
        spread=active/12
        mean=sum(densities)/12
        contrast=(sum((value-mean)**2 for value in densities)/12)**.5
        protected=1-densities[self.protected_region]
        styles=len(style_counts or {})
        variety=min(1,styles/12)
        crossings=min(1,float(intersections or 0)/42)
        motif_depth=min(1,float(motif_count or 0)/24)
        repetition=float(o.get("repetition",0) or 0)
        milestones=self.milestones()

        score=clamp(
            spread*.16+
            min(1,contrast*2.2)*.17+
            protected*.15+
            variety*.14+
            crossings*.10+
            motif_depth*.11+
            milestones["ratio"]*.17-
            max(0,repetition-.56)*.22,
            0,1,
        )

        if protected<.28:need="RECOVER_AIR"
        elif spread<.4:need="EXPAND_FIELD"
        elif contrast<.11:need="CREATE_COUNTERPOINT"
        elif repetition>.58:need="BREAK_REPETITION"
        elif crossings<.14 and spread>.48:need="CONNECT_ISLANDS"
        elif milestones["primary"] and milestones["secondary"] and not milestones["interrupt"]:need="INTERRUPT_ORDER"
        elif milestones["interrupt"] and not milestones["return"]:need="RETURN_TO_MEMORY"
        elif not milestones["edit"]:need="EDIT_OVERWORK"
        elif score>.74 and milestones["finish_ready"]:need="RESOLVE"
        else:need="DEVELOP"

        return DirectorSnapshot(
            composition_score=round(score,3),
            regional_spread=round(spread,3),
            density_contrast=round(contrast,3),
            protected_space=round(protected,3),
            need=need,
            milestone_ratio=milestones["ratio"],
            finish_ready=bool(milestones["finish_ready"]),
        )

    def plan(self,phase,o,decision,*,force=False,style_counts=None,intersections=0,motif_count=0):
        snapshot=self.evaluate(o,style_counts,intersections,motif_count)
        phase_changed=phase!=self.last_phase
        self.last_phase=phase

        critical=snapshot.need in ("RECOVER_AIR","BREAK_REPETITION")
        if self.current and self.burst_remaining>0 and not force and not phase_changed and not critical:
            self.burst_remaining-=1
            return self.current

        pass_name=self._choose_pass(phase,snapshot,int(decision))
        if snapshot.need=="INTERRUPT_ORDER" and phase in ("CONTRAST","REFINEMENT","RESOLUTION"):pass_name="INTERRUPT"
        elif snapshot.need=="RETURN_TO_MEMORY" and phase in ("DEVELOPMENT","CONTRAST","REFINEMENT","RESOLUTION"):pass_name="RETURN"
        elif snapshot.need=="EDIT_OVERWORK" and phase in ("REFINEMENT","RESOLUTION"):pass_name="EDIT"

        densities=self._densities(o)
        visited=self._visited_regions(o)
        scores=[self._score_region(i,pass_name,densities,visited,o) for i in range(12)]

        if snapshot.need=="RECOVER_AIR":
            candidates=[i for i in range(12) if i!=self.protected_region]
            target=min(candidates,key=lambda i:densities[i])
        elif snapshot.need in ("CREATE_COUNTERPOINT","INTERRUPT_ORDER"):
            target=self.counter_region
        elif snapshot.need=="EXPAND_FIELD":
            target=min(range(12),key=lambda i:(densities[i],self.region_visits[i]))
        elif snapshot.need=="BREAK_REPETITION":
            target=max(range(12),key=lambda i:scores[i]+(.28 if i==self.counter_region else 0))
        elif pass_name=="RETURN":
            target=min(self.primary_regions,key=lambda i:abs(densities[i]-.48))
        else:
            target=max(range(12),key=lambda i:scores[i])

        self.region_visits[target]+=1
        center=REGION_CENTERS[target]
        jitter=16 if pass_name in ("RETURN","EDIT","RESOLVE") else 22
        target_point=[
            clamp(center[0]+self.rng.uniform(-jitter,jitter),42,758),
            clamp(center[1]+self.rng.uniform(-jitter,jitter),42,458),
        ]

        style_pool=PASS_STYLES[pass_name]
        if snapshot.need=="BREAK_REPETITION":
            style_pool=("cross","fracture","segmented","jitter","hook")
        elif snapshot.need=="CONNECT_ISLANDS":
            style_pool=("web","branch","sweep","lattice","cross")
        elif snapshot.need=="RECOVER_AIR":
            style_pool=("accent","contour","hook","curl","sweep")

        strategy=PASS_STRATEGY[pass_name]
        if snapshot.need=="BREAK_REPETITION":strategy="CONTRADICT"
        elif snapshot.need=="CONNECT_ISLANDS":strategy="CONNECT"
        elif snapshot.need=="RECOVER_AIR":strategy="ESCAPE"

        scale_multiplier={
            "SCOUT":.78,
            "BLOCK_IN":1.32,
            "PRIMARY_FORMS":1.18,
            "SECONDARY_RHYTHMS":.96,
            "INTERRUPT":1.12,
            "RETURN":.82,
            "EDIT":.62,
            "RESOLVE":.55,
        }[pass_name]

        # Hold macro intentions much longer so forms can accumulate before the next strategy switch.
        burst=self.rng.randint(18,50)
        if pass_name in ("EDIT","RESOLVE"):burst=self.rng.randint(12,28)
        elif pass_name=="INTERRUPT":burst=self.rng.randint(14,30)
        elif pass_name=="RETURN":burst=self.rng.randint(16,36)

        self.burst_remaining=burst-1
        self.plan_index+=1
        self.pass_counts[pass_name]+=1

        self.current={
            "index":self.plan_index,
            "pass":pass_name,
            "need":snapshot.need,
            "strategy":strategy,
            "target_region":target,
            "target_point":[round(target_point[0],3),round(target_point[1],3)],
            "style_pool":style_pool,
            "preferred_style":self.rng.choice(style_pool),
            "transform_pool":PASS_TRANSFORMS[pass_name],
            "scale_multiplier":scale_multiplier,
            "preserve_region":self.protected_region,
            "composition_score":snapshot.composition_score,
            "regional_spread":snapshot.regional_spread,
            "milestone_ratio":snapshot.milestone_ratio,
            "finish_ready":snapshot.finish_ready,
            "macro_intent":f"{pass_name}:{snapshot.need}",
            "burst_size":burst,
            "decision":int(decision),
        }
        self.plan_history.append(dict(self.current))
        self.plan_history=self.plan_history[-96:]
        return self.current
