"""Authoritative deterministic canvas mechanics for JPGFLY.

The browser may render these events, but it does not choose or author them.
"""
from __future__ import annotations
import math

CANVAS_WIDTH=800
CANVAS_HEIGHT=500
MARGIN=24

def clamp(value,low,high):return max(low,min(high,value))
def rnd(value,places=3):return float(f"{float(value):.{places}f}")
def distance(a,b):return math.hypot(b[0]-a[0],b[1]-a[1])
def orientation(a,b,c):return (b[1]-a[1])*(c[0]-b[0])-(b[0]-a[0])*(c[1]-b[1])
def intersects(a,b,c,d):return orientation(a,b,c)*orientation(a,b,d)<0 and orientation(c,d,a)*orientation(c,d,b)<0

FIGURE_SHAPES={
"FLY":[[0,0],[10,-8],[20,-5],[28,0],[20,5],[10,8],[0,0],[-10,-13],[-24,-18],[-18,-4],[0,0],[-10,13],[-24,18],[-18,4],[0,0],[18,-14],[30,-18],[23,-3],[0,0],[18,14],[30,18],[23,3],[0,0],[34,0]],
"CAT_FACE":[[0,0],[8,-13],[16,-5],[28,-12],[40,-5],[48,-13],[56,0],[58,18],[50,31],[38,38],[20,38],[7,31],[0,18],[0,0],[14,13],[19,9],[24,13],[29,9],[34,13],[41,18],[34,22],[28,18],[23,23],[17,18],[9,21],[0,20],[-10,18]],
"FISH":[[0,0],[12,-12],[28,-18],[45,-14],[58,0],[45,14],[28,18],[12,12],[0,0],[-17,-14],[-12,0],[-17,14],[0,0],[42,0],[47,-3],[50,0],[47,3],[42,0]],
"TV":[[0,0],[0,-30],[48,-30],[48,6],[0,6],[0,0],[12,-5],[36,-5],[36,-21],[12,-21],[12,-5],[24,-30],[17,-42],[24,-30],[32,-43],[24,-30]],
"GHOST":[[0,0],[0,-20],[7,-34],[18,-41],[31,-39],[41,-29],[46,-13],[44,7],[36,1],[29,8],[22,1],[15,8],[8,1],[0,7],[0,0],[13,-18],[17,-22],[21,-18],[29,-18],[33,-22],[37,-18]],
"SNAIL":[[0,0],[14,-5],[28,-5],[40,0],[48,7],[53,7],[57,3],[60,7],[53,7],[45,14],[30,17],[15,15],[0,9],[0,0],[16,5],[28,1],[35,7],[31,13],[21,14],[14,9],[16,5]],
"DUCK":[[0,0],[12,-10],[27,-12],[38,-6],[46,-11],[56,-9],[48,-3],[57,2],[46,4],[39,12],[25,17],[10,15],[0,8],[0,0],[33,-8],[35,-13],[38,-8]],
"MOUSE":[[0,0],[7,-14],[16,-20],[24,-14],[31,-21],[40,-15],[47,-4],[48,10],[42,22],[31,29],[18,28],[7,21],[0,10],[0,0],[13,4],[18,0],[23,4],[30,3],[35,0],[40,3],[47,8],[58,7],[66,2]],
"SPIDER":[[0,0],[12,-8],[24,0],[12,8],[0,0],[-12,-14],[-26,-19],[-12,-4],[0,0],[-16,0],[-30,-3],[0,0],[-12,14],[-26,19],[0,4],[24,0],[36,-15],[24,0],[38,0],[24,0],[36,15]],
"MOTH":[[0,0],[12,-8],[25,-20],[39,-13],[31,-1],[18,4],[31,9],[39,21],[25,25],[12,12],[0,0],[-12,-8],[-25,-20],[-39,-13],[-31,-1],[-18,4],[-31,9],[-39,21],[-25,25],[-12,12],[0,0]],
"BEETLE":[[0,0],[10,-13],[24,-18],[38,-12],[46,0],[38,12],[24,18],[10,13],[0,0],[23,0],[46,0],[23,0],[11,-18],[1,-27],[11,-18],[35,-18],[45,-27],[35,-18],[11,18],[1,27],[11,18],[35,18],[45,27]],
"BIRD_HEAD":[[0,0],[10,-15],[25,-23],[40,-18],[51,-7],[61,-4],[51,1],[40,4],[36,16],[24,24],[10,19],[0,8],[0,0],[34,-10],[38,-13],[42,-10],[38,-7],[34,-10]],
"PHONE":[[0,0],[0,-35],[28,-35],[28,10],[0,10],[0,0],[6,-29],[22,-29],[22,2],[6,2],[6,-29],[14,6],[16,6]],
"KEY":[[0,0],[10,-10],[21,-10],[31,0],[21,10],[10,10],[0,0],[31,0],[55,0],[55,7],[63,7],[63,0],[70,0]],
"CLOCK":[[0,0],[8,-14],[23,-21],[39,-17],[49,-5],[51,11],[44,25],[30,33],[14,30],[2,19],[0,0],[25,5],[25,-10],[25,5],[37,13]],
"EYEBALL":[[0,0],[12,-10],[28,-15],[45,-10],[58,0],[45,10],[28,15],[12,10],[0,0],[18,0],[28,-7],[38,0],[28,7],[18,0]],
"BOTTLE":[[0,0],[8,-8],[8,-25],[14,-31],[14,-42],[26,-42],[26,-31],[32,-25],[32,-8],[40,0],[40,28],[0,28],[0,0],[12,8],[28,8],[28,21],[12,21],[12,8]],
"WINDOW":[[0,0],[0,-36],[48,-36],[48,0],[0,0],[24,0],[24,-36],[24,-18],[0,-18],[48,-18]],
"LAMP":[[0,0],[12,-10],[24,-28],[36,-10],[48,0],[0,0],[24,0],[24,24],[10,30],[38,30],[24,24]],
"MASK":[[0,0],[10,-17],[25,-24],[41,-20],[52,-7],[54,10],[46,23],[31,29],[15,25],[3,14],[0,0],[14,2],[19,-3],[24,2],[31,2],[36,-3],[41,2],[34,14],[27,18],[20,14]],
}

FIGURE_SHAPES.update({
"WEIRD_FACE":[[0,0],[7,-16],[20,-26],[38,-25],[52,-14],[58,2],[55,19],[42,31],[24,34],[8,26],[0,12],[0,0],[12,2],[17,-4],[22,2],[34,1],[40,-5],[46,1],[39,16],[30,21],[21,17],[13,21],[7,15],[0,12]],
"WING":[[0,0],[12,-11],[28,-18],[46,-15],[61,-4],[50,4],[33,8],[18,7],[0,0],[16,1],[34,-2],[50,-4]],
"FLOWER":[[0,0],[10,-9],[18,-21],[26,-9],[38,-14],[34,0],[45,9],[30,13],[25,28],[16,16],[3,22],[6,7],[0,0],[20,4],[30,0],[20,-4],[10,0],[20,4]],
"MEAT_BLOB":[[0,0],[7,-15],[20,-25],[36,-22],[48,-10],[54,5],[47,21],[33,29],[17,26],[4,17],[0,0],[13,-3],[23,-10],[34,-7],[41,4],[35,14],[22,18],[10,12],[0,0]],
"BONE":[[0,0],[8,-9],[16,-8],[24,0],[42,0],[50,-8],[58,-9],[66,0],[58,9],[50,8],[42,0],[24,0],[16,8],[8,9],[0,0]],
"CROWN":[[0,0],[8,-27],[20,-11],[31,-32],[42,-11],[55,-27],[62,0],[0,0],[8,11],[54,11],[62,0]],
})

# Broader literal form vocabulary. These are deliberately simple line primitives:
# the painting agent can repeat, distort, mirror, erase, overpaint and combine them.
FIGURE_SHAPES.update({
"CIRCLE":[[0,0],[7,-12],[20,-18],[34,-17],[46,-8],[52,5],[48,18],[37,28],[22,31],[8,25],[0,14],[0,0]],
"TRIANGLE":[[0,0],[28,-42],[58,0],[0,0]],
"SQUARE":[[0,0],[0,-42],[42,-42],[42,0],[0,0]],
"RECTANGLE":[[0,0],[0,-30],[62,-30],[62,0],[0,0]],
"DIAMOND":[[0,0],[28,-36],[56,0],[28,36],[0,0]],
"HEXAGON":[[0,0],[14,-24],[42,-24],[56,0],[42,24],[14,24],[0,0]],
"OCTAGON":[[0,0],[11,-22],[31,-31],[51,-22],[62,0],[51,22],[31,31],[11,22],[0,0]],
"STAR":[[0,0],[12,-11],[17,-29],[27,-14],[46,-14],[32,-2],[38,17],[22,7],[7,18],[12,0],[0,0]],
"CRESCENT":[[0,0],[10,-16],[25,-24],[42,-21],[55,-10],[62,4],[55,17],[41,27],[24,29],[10,21],[0,8],[0,0],[12,1],[22,10],[36,12],[48,6],[56,-3]],
"SPIRAL_PORTAL":[[0,0],[9,-11],[24,-16],[39,-11],[48,0],[48,14],[39,25],[25,30],[12,26],[4,17],[4,7],[11,0],[21,-3],[31,0],[36,7],[35,14],[29,19],[21,20],[15,16],[13,10],[16,6],[22,5]],
"MAZE":[[0,0],[0,-34],[58,-34],[58,24],[12,24],[12,-22],[46,-22],[46,12],[24,12],[24,-10],[36,-10],[36,2]],
"GRID":[[0,0],[0,-42],[54,-42],[54,18],[0,18],[0,0],[18,0],[18,-42],[18,18],[36,18],[36,-42],[54,-42],[54,-22],[0,-22]],
"CUBE":[[0,0],[0,-34],[38,-34],[38,4],[0,4],[0,0],[14,-14],[52,-14],[52,-48],[14,-48],[14,-14],[38,4],[52,-14],[38,-34],[52,-48]],
"PYRAMID":[[0,0],[31,-48],[62,0],[0,0],[15,0],[31,-48],[47,0],[31,-18],[0,0]],
"ARCH":[[0,0],[0,-24],[7,-38],[20,-46],[35,-46],[48,-38],[55,-24],[55,0],[44,0],[44,-23],[38,-31],[28,-35],[18,-31],[11,-23],[11,0],[0,0]],
"TUNNEL":[[0,0],[4,-18],[15,-32],[30,-38],[46,-32],[57,-18],[61,0],[50,0],[47,-13],[39,-21],[30,-25],[21,-21],[13,-13],[11,0],[0,0]],
"HOUSE":[[0,0],[0,-32],[28,-53],[56,-32],[56,10],[0,10],[0,0],[18,10],[18,-12],[37,-12],[37,10],[56,10]],
"DOOR":[[0,0],[0,-50],[34,-50],[34,8],[0,8],[0,0],[27,-18],[29,-18]],
"STAIRCASE":[[0,0],[14,0],[14,-10],[28,-10],[28,-20],[42,-20],[42,-30],[56,-30],[56,-40],[70,-40]],
"LADDER":[[0,0],[8,-50],[8,8],[8,-40],[38,-40],[8,-40],[8,-25],[38,-25],[8,-25],[8,-10],[38,-10],[38,-50],[38,8]],
"TABLE":[[0,0],[0,-20],[62,-20],[62,0],[0,0],[9,0],[9,34],[9,0],[52,0],[52,34]],
"BED":[[0,0],[0,-21],[64,-21],[64,8],[0,8],[0,0],[12,-21],[12,-38],[30,-38],[30,-21],[6,8],[6,24],[6,8],[58,8],[58,24]],
"CHAIR":[[0,0],[0,-30],[0,8],[32,8],[32,-8],[0,-8],[6,8],[6,34],[6,8],[27,8],[27,34]],
"ELEVATOR":[[0,0],[0,-54],[46,-54],[46,8],[0,8],[0,0],[23,8],[23,-54],[9,-44],[37,-44]],
"CAGE":[[0,0],[0,-42],[54,-42],[54,14],[0,14],[0,0],[13,14],[13,-42],[27,-42],[27,14],[41,14],[41,-42]],
"EGG":[[0,0],[7,-18],[20,-33],[34,-36],[47,-28],[56,-12],[58,7],[50,25],[35,34],[19,31],[7,19],[0,0]],
"SHELL":[[0,0],[12,-10],[28,-12],[42,-5],[50,8],[46,21],[35,30],[21,30],[8,22],[0,10],[0,0],[14,6],[25,2],[34,7],[35,16],[29,22],[20,22],[14,16],[14,9]],
"HAND":[[0,0],[10,-18],[15,-43],[21,-43],[22,-17],[27,-50],[33,-49],[31,-16],[38,-46],[44,-44],[39,-13],[48,-35],[53,-32],[46,-6],[54,4],[49,18],[34,27],[18,25],[6,16],[0,0]],
"FOOT":[[0,0],[9,-9],[24,-11],[43,-4],[58,4],[63,12],[57,20],[43,22],[28,17],[13,14],[0,14],[0,0]],
"SKULL":[[0,0],[5,-19],[18,-32],[36,-35],[52,-26],[60,-10],[56,7],[46,17],[44,31],[13,31],[12,18],[4,10],[0,0],[15,-7],[21,-12],[27,-7],[34,-7],[40,-12],[46,-7],[25,8],[31,12],[37,8],[20,20],[47,20]],
"HEART":[[0,0],[8,-13],[21,-17],[31,-9],[40,-17],[54,-14],[62,-2],[59,12],[46,27],[31,42],[15,27],[3,12],[0,0]],
"MOUTH":[[0,0],[13,-8],[30,-11],[48,-7],[62,1],[48,10],[30,13],[13,9],[0,0],[13,1],[30,4],[48,1],[62,1]],
"NOSE":[[0,0],[20,-34],[31,-3],[23,7],[12,5],[0,0],[31,-3],[40,3]],
"EAR":[[0,0],[6,-20],[19,-32],[34,-28],[43,-15],[41,4],[31,18],[18,25],[6,18],[0,7],[0,0],[12,-3],[20,-14],[30,-12],[33,-3],[27,8],[18,11]],
"RIBCAGE":[[0,0],[28,-42],[28,34],[28,-30],[10,-25],[2,-12],[7,0],[21,5],[28,0],[28,-20],[46,-25],[54,-12],[49,0],[35,5],[28,0],[28,14],[12,12],[6,22],[17,29],[28,25],[28,14],[44,12],[50,22],[39,29],[28,25]],
"DOG_FACE":[[0,0],[8,-20],[20,-31],[37,-28],[50,-18],[58,-1],[55,18],[44,31],[28,36],[12,29],[2,16],[0,0],[8,-20],[-6,-34],[-10,-10],[8,-20],[50,-18],[65,-33],[68,-7],[50,-18],[18,3],[23,-1],[28,3],[36,3],[41,-1],[46,3],[25,17],[35,21],[44,16]],
"RABBIT_HEAD":[[0,0],[9,-19],[16,-56],[27,-61],[31,-22],[39,-60],[51,-55],[48,-16],[57,-4],[58,14],[49,29],[35,37],[20,34],[7,24],[0,10],[0,0],[16,3],[22,-2],[27,3],[36,3],[42,-2],[47,3],[31,17]],
"BAT":[[0,0],[14,-8],[25,-23],[36,-12],[47,-28],[59,-10],[70,-18],[63,1],[48,7],[36,3],[25,8],[10,2],[0,0],[34,-8],[36,-22],[39,-8]],
"SNAKE":[[0,0],[12,-10],[26,-8],[38,1],[50,5],[61,-3],[70,-14],[77,-11],[72,-3],[77,4],[68,5],[58,13],[46,15],[33,9],[21,0],[10,1],[0,8]],
"WORM":[[0,0],[9,-8],[19,-10],[29,-4],[40,4],[50,6],[59,0],[67,-9],[75,-8],[81,-2]],
"JELLYFISH":[[0,0],[8,-18],[23,-29],[39,-28],[53,-17],[60,0],[0,0],[8,5],[6,28],[14,8],[19,5],[18,33],[26,8],[31,5],[33,29],[40,8],[46,5],[50,31],[55,6],[60,0]],
"OCTOPUS":[[0,0],[8,-20],[22,-31],[38,-31],[52,-20],[60,0],[54,12],[45,17],[37,15],[30,10],[23,16],[13,15],[5,9],[0,0],[13,15],[3,29],[17,22],[23,16],[20,34],[31,22],[37,15],[44,33],[45,17],[58,29]],
"CRAB":[[0,0],[12,-10],[25,-12],[38,-10],[50,0],[38,10],[25,12],[12,10],[0,0],[-12,-9],[-20,-19],[-13,-3],[0,0],[-14,11],[-23,20],[-12,4],[50,0],[64,-10],[72,-20],[65,-3],[50,0],[65,11],[74,20],[63,4]],
"SUN":[[0,0],[12,-16],[28,-22],[44,-16],[56,0],[44,16],[28,22],[12,16],[0,0],[28,-22],[28,-38],[28,-22],[56,0],[72,0],[56,0],[28,22],[28,38],[28,22],[0,0],[-16,0],[0,0],[8,-16],[-4,-28],[8,-16],[48,-16],[60,-28],[48,-16],[48,16],[60,28],[48,16],[8,16],[-4,28]],
"MOON":[[0,0],[9,-18],[24,-28],[42,-28],[56,-19],[64,-4],[62,12],[52,25],[38,32],[21,30],[8,20],[0,6],[0,0],[13,0],[25,8],[39,8],[51,1],[58,-9]],
"PLANET":[[0,0],[8,-15],[22,-23],[38,-22],[51,-12],[58,3],[53,18],[40,28],[24,29],[10,21],[0,8],[0,0],[-11,12],[14,5],[38,-2],[66,-9],[76,-7],[61,2],[40,10],[15,17],[-6,20]],
"COMET":[[0,0],[12,-10],[27,-11],[39,-3],[42,9],[34,20],[20,24],[7,18],[0,8],[0,0],[-18,3],[-38,11],[-57,19],[-35,4],[-56,-7],[-32,-1],[-52,-20],[-24,-8],[0,0]],
"CANDLE":[[0,0],[0,-42],[20,-42],[20,0],[0,0],[10,-42],[4,-53],[10,-65],[16,-53],[10,-42]],
"CUP":[[0,0],[0,-30],[40,-30],[38,6],[3,6],[0,0],[40,-22],[56,-20],[58,-7],[50,1],[38,0]],
"FORK":[[0,0],[0,-54],[0,-34],[8,-34],[8,-54],[8,-34],[16,-34],[16,-54],[16,-34],[24,-34],[24,-54],[24,-34],[12,-22],[12,18]],
})

FIGURE_MOTIFS=set(FIGURE_SHAPES)

def style_offset(style,t,index):
    if style=="loop":return 5.3+math.sin(t*math.pi*4)*2.8
    if style=="spiral":return 2.8+t*6.4+math.sin(t*math.pi*6)*1.4
    if style=="jitter":return (1 if index%2 else -1)*(5.4+t*3.1)
    if style=="segmented":return 7.2 if index%3==0 else -2.8
    if style=="branch":return (-4.8 if t>.52 else 3.6)*math.sin(t*math.pi*2)
    if style=="cross":return math.sin(t*math.pi*4)*10.5
    if style=="echo":return 1.4+math.sin(t*math.pi*6)*3.8
    if style=="cluster":return 4.4+math.sin(t*math.pi*10)*5.6
    if style=="contour":return 1.2+math.sin(t*math.pi*5)*2.7
    if style=="knot":return 4.8+math.sin(t*math.pi*8)*6.2
    if style=="fracture":return 8.4 if index%4<2 else -7.1
    if style=="orbit":return 6.1+math.sin(t*math.pi*3)*2.4
    if style=="web":return math.sin(t*math.pi*12)*8.8+(5 if index%5==0 else -1.2)
    if style=="coil":return 5.7+t*5.2+math.sin(t*math.pi*10)*2.2
    if style=="petal":return math.sin(t*math.pi*4)*7.4+math.cos(t*math.pi*2)*2.4
    if style=="lattice":return 9.2 if index%4==0 else (-4.8 if index%2 else 3.6)
    if style=="hook":return .7 if t<.58 else 9.8*math.sin((t-.58)/.42*math.pi)
    if style=="starburst":return 12.4 if index%5==0 else -2.9
    if style=="wave":return math.sin(t*math.pi*6)*6.2
    if style=="zigzag":return 10.5 if index%2==0 else -10.5
    if style=="ribbon":return math.sin(t*math.pi*4)*8.4+math.sin(t*math.pi*9)*2.1
    if style=="vortex":return 3.0+t*8.5+math.sin(t*math.pi*8)*2.6
    if style=="rosette":return math.sin(t*math.pi*10)*7.8
    if style=="maze":return 8.8 if index%4 in (0,1) else -8.8
    if style=="meander":return math.sin(t*math.pi*3)*5.4+(4.6 if index%6<3 else -4.6)
    if style=="blob":return math.sin(t*math.pi*7)*5.8+math.cos(t*math.pi*5)*4.1
    if style=="fan":return (index%7-3)*2.1
    if style=="helix":return math.sin(t*math.pi*12)*(2.5+t*5.5)
    if style=="scallop":return abs(math.sin(t*math.pi*6))*8.1-3.8
    if style=="scribble":return math.sin(index*2.47+t*math.pi*13)*9.7
    if style=="accent":return math.sin(t*math.pi)*.22
    if style=="bold":return math.sin(t*math.pi)*.34
    if style=="sweep":return math.sin(t*math.pi)*.72
    return 0

def motif_offset(motif,t,index):
    motif=motif or "NONE"
    if motif=="BANANA_CURVE":return math.sin(t*math.pi)*1.45
    if motif=="PHALLIC_SPIRAL":return .08 if t<.55 else 2.9+math.sin((t-.55)/.45*math.pi*4)*1.15
    if motif=="PAIRED_FLIES":return math.sin(t*math.pi*4)*2.25
    if motif=="MATING_DANCE":return math.sin(t*math.pi*6)*2.65+math.sin(t*math.pi*2)*.75
    if motif=="WEIRD_FACE":return math.sin(t*math.pi*4)*2.4+math.cos(t*math.pi*2)*.8
    if motif=="UNDERWEAR":return 1.2 if index%4<2 else -1.2
    if motif=="CROWN":return 2.25 if index%3==0 else -1.05
    if motif=="CENSORED_MARK":return 0
    if motif=="SLIME":return math.sin(t*math.pi*7)*1.55+(1.1 if t>.7 else 0)
    if motif=="MEAT_BLOB":return math.sin(t*math.pi*5)*2+math.cos(t*math.pi*3)
    if motif=="OOZE":return math.sin(t*math.pi*8)*1.15+t*1.2
    if motif=="EYE":return math.sin(t*math.pi*4)*1.75
    if motif=="WING":return math.sin(t*math.pi*3)*1.35
    if motif=="TOOTH":return 1.65 if index%3==0 else -.55
    if motif=="FLOWER":return math.sin(t*math.pi*6)*1.8
    if motif=="BONE":return 1.3 if index%5==0 else -.25
    if motif=="CHAIR":return 1.5 if index%4==0 else 0
    if motif=="SHOE":return 1.5*math.sin((t-.55)/.45*math.pi) if t>.55 else .2
    if motif=="TRASH":return math.sin(index*2.13)*1.3
    return 0

def family_for(style):
    return {"curl":"cubic_bezier","segmented":"segmented_lines","branch":"branching","cross":"self_intersection","echo":"repeated_motif","cluster":"dense_cluster","knot":"knotted_orbit","fracture":"fractured_zigzag","orbit":"orbital_loop","web":"woven_web","coil":"coiled_form","petal":"petal_oscillation","lattice":"angular_lattice","hook":"hooked_turn","starburst":"radial_burst","wave":"wave_field","zigzag":"angular_zigzag","ribbon":"ribbon_curve","vortex":"vortex_curve","rosette":"rosette_loop","maze":"maze_turn","meander":"meandering_line","blob":"biomorphic_blob","fan":"fan_rays","helix":"helical_trace","scallop":"scalloped_curve","scribble":"automatic_scribble"}.get(style,style)

def brush_profile(tool,pressure):
    base=.8+pressure*6.4
    profiles={"ink_line":(1,.92),"soft_paint":(2.15,.72),"dry_brush":(1.45,.76),"fine_pen":(.42,.98),"charcoal_grain":(1.35,.78),"wash":(3.1,.62),"stipple":(.78,.92),"splatter":(.7,.88),"subtractive":(1.7,1)}
    width,opacity=profiles.get(tool,profiles["ink_line"])
    return {"baseWidth":rnd(base,2),"width":rnd(base*width,2),"opacity":rnd(opacity*(.9+pressure*.1),3)}

def rotate_point(point,angle,scale,start):
    x,y=point[0]*scale,point[1]*scale;cs,sn=math.cos(angle),math.sin(angle)
    return [clamp(rnd(start[0]+x*cs-y*sn),MARGIN,CANVAS_WIDTH-MARGIN),clamp(rnd(start[1]+x*sn+y*cs),MARGIN,CANVAS_HEIGHT-MARGIN)]

def figurative_primitive(motif,start,heading,movement_distance):
    local=FIGURE_SHAPES.get(motif)
    if not local:return None
    size=clamp(movement_distance/90,.62,1.55)
    local_length=sum(math.hypot(local[i][0]-local[i-1][0],local[i][1]-local[i-1][1]) for i in range(1,len(local))) or 1
    physical_scale=min(size,(movement_distance*1.85)/local_length)
    return [rotate_point(point,heading,physical_scale,start) for point in local]

class CanvasMemory:
    def __init__(self,columns=16,rows=10):
        self.columns=columns;self.rows=rows;self.grid=[0]*(columns*rows);self.segments=[];self.paths=[];self.visits=[]
        self.intersections=0;self.drawnLength=0;self.erasedLength=0;self.meaningfulChanges=0;self.consecutiveLowChange=0
        self.familyCounts={};self.focalAreas=[];self.directionBins=[0]*12;self.lastChange=0
    def cell(self,point):
        column=int(clamp(math.floor(point[0]/CANVAS_WIDTH*self.columns),0,self.columns-1));row=int(clamp(math.floor(point[1]/CANVAS_HEIGHT*self.rows),0,self.rows-1))
        return column,row,row*self.columns+column
    def cell_center(self,index):
        return [((index%self.columns)+.5)/self.columns*CANVAS_WIDTH,(math.floor(index/self.columns)+.5)/self.rows*CANVAS_HEIGHT]
    def negative_space(self,origin):
        minimum=min(self.grid);candidates=[i for i,v in enumerate(self.grid) if v==minimum];best=candidates[0] if candidates else 0
        for index in candidates:
            if distance(origin,self.cell_center(index))>distance(origin,self.cell_center(best)):best=index
        return self.cell_center(best)
    def focal_point(self):
        if not self.focalAreas:return [CANVAS_WIDTH/2,CANVAS_HEIGHT/2]
        return list(max(self.focalAreas,key=lambda item:item["weight"])["point"])
    def nearby(self,point,radius=76):
        return sum(1 for path in self.paths[-32:] if any(distance(point,other)<=radius for other in path))
    def remember(self,points,family,erase=False):
        visited=set();new_cells=0;new_intersections=0;length=0
        for point in points:
            _,_,index=self.cell(point)
            if index not in visited and self.grid[index]==0:new_cells+=1
            visited.add(index)
            if not erase:self.grid[index]+=1
        for i in range(1,len(points)):
            segment=[points[i-1],points[i]];length+=distance(*segment)
            if not erase:
                angle=(math.atan2(segment[1][1]-segment[0][1],segment[1][0]-segment[0][0])+math.tau)%math.tau
                self.directionBins[int(math.floor(angle/math.tau*len(self.directionBins)))%len(self.directionBins)]+=1
                for j in range(max(0,len(self.segments)-650),len(self.segments),3):
                    if intersects(segment[0],segment[1],self.segments[j][0],self.segments[j][1]):new_intersections+=1
                self.segments.append(segment)
        if erase:self.erasedLength+=length
        else:self.drawnLength+=length
        self.intersections+=new_intersections;self.familyCounts[family]=self.familyCounts.get(family,0)+1
        self.paths.append([list(p) for p in points]);self.visits.append(list(points[-1]))
        midpoint=points[len(points)//2];self.focalAreas.append({"point":list(midpoint),"weight":length+new_intersections*18})
        self.focalAreas=sorted(self.focalAreas,key=lambda item:item["weight"],reverse=True)[:12]
        change=new_cells*1.8+new_intersections*1.25+min(2,length/65)+(.5 if erase else 0);meaningful=change>=1.35;self.lastChange=rnd(change)
        if meaningful:self.meaningfulChanges+=1;self.consecutiveLowChange=0
        else:self.consecutiveLowChange+=1
        return {"meaningful":meaningful,"change":rnd(change),"newCells":new_cells,"newIntersections":new_intersections,"length":rnd(length)}
    def observe(self,current_position,elapsed,decision_count,physical_action_count):
        occupied=sum(1 for value in self.grid if value);total=len(self.grid)
        left=sum(1 for i,value in enumerate(self.grid) if value and i%self.columns<self.columns/2);right=occupied-left
        max_density=max(self.grid) if self.grid else 0;family_total=sum(self.familyCounts.values());repetition=(max(self.familyCounts.values())/family_total) if family_total else 0
        quadrants=[0,0,0,0]
        for index,value in enumerate(self.grid):
            column=index%self.columns;row=math.floor(index/self.columns);quadrants[(2 if row>=self.rows/2 else 0)+(1 if column>=self.columns/2 else 0)]+=value
        quadrant_max=max(1,*quadrants);mean=sum(quadrants)/4;contrast=math.sqrt(sum((v-mean)**2 for v in quadrants)/4)/quadrant_max
        direction_total=sum(self.directionBins);dominant_bin=self.directionBins.index(max(self.directionBins)) if self.directionBins else 0;_,_,current_cell=self.cell(current_position)
        regions=[0]*12
        for index,value in enumerate(self.grid):
            column=index%self.columns;row=math.floor(index/self.columns)
            region_column=min(3,int(column/self.columns*4));region_row=min(2,int(row/self.rows*3))
            regions[region_row*4+region_column]+=value
        region_peak=max(1,*regions)
        region_density=[rnd(value/region_peak) for value in regions]
        region_mean=sum(region_density)/12
        regional_contrast=rnd(math.sqrt(sum((value-region_mean)**2 for value in region_density)/12))
        occupied_regions=sum(1 for value in region_density if value>.08)
        return {"currentForelegPosition":list(current_position),"canvasOccupancy":rnd(occupied/total),"negativeSpace":self.negative_space(current_position),"focalArea":self.focal_point(),"nearbyLines":self.nearby(current_position),"intersections":self.intersections,"densityPeak":max_density,"densityBalance":rnd(1-abs(left-right)/occupied) if occupied else 1,"repetition":rnd(repetition),"recentMarks":[path[-3:] for path in self.paths[-4:]],"visitedAreas":self.visits[-48:],"familyCounts":dict(self.familyCounts),"meaningfulChangeRate":rnd(self.meaningfulChanges/len(self.paths)) if self.paths else 1,"consecutiveLowChange":self.consecutiveLowChange,"elapsedDrawingTime":elapsed,"decisionCount":decision_count,"physicalActionCount":physical_action_count,"quadrantDensity":[rnd(v/quadrant_max) for v in quadrants],"regionDensity":region_density,"occupiedRegions":occupied_regions,"regionalContrast":regional_contrast,"densityContrast":rnd(contrast),"localDensity":rnd(self.grid[current_cell]/max_density) if max_density else 0,"dominantDirection":rnd((dominant_bin+.5)/len(self.directionBins)*math.tau),"directionalUniformity":rnd(max(self.directionBins)/direction_total) if direction_total else 0,"lastCompositionalChange":self.lastChange}

class ServerCanvasMechanics:
    def __init__(self,seed,session_id):
        self.seed=int(seed)&0xffffffff;self.events=[{"type":"session_start","sessionId":session_id,"timestamp":0},{"type":"clear","timestamp":20}]
        self.memory=CanvasMemory();self.position=[735.0,48.0];self.brushDown=False;self.clock=100;self.physicalActionCount=0
    def observe(self,decision_count):return self.memory.observe(self.position,self.clock,decision_count,self.physicalActionCount)
    def execute(self,action,decision_index):
        start=list(self.position);count=int(clamp(round(18+float(action["movementDistance"])/2.7+int(action.get("branchingDepth") or 0)*4),18,96))
        figure=figurative_primitive(action.get("motifHint"),start,float(action["targetDirection"]),float(action["movementDistance"])) if action.get("brushDown") and action.get("motifHint") in FIGURE_MOTIFS else None
        points=figure or [start]
        if figure is None:
            step=float(action["movementDistance"])/(count-1);heading=float(action["targetDirection"])
            for i in range(1,count):
                t=i/(count-1);heading+=float(action["curvature"])/(count-1)+(style_offset(action["movementStyle"],t,i)+motif_offset(action.get("motifHint"),t,i)*3.2)/(count-1)
                x=points[-1][0]+math.cos(heading)*step;y=points[-1][1]+math.sin(heading)*step
                if x<MARGIN or x>CANVAS_WIDTH-MARGIN:heading=math.pi-heading
                if y<MARGIN or y>CANVAS_HEIGHT-MARGIN:heading=-heading
                x=clamp(points[-1][0]+math.cos(heading)*step,MARGIN,CANVAS_WIDTH-MARGIN);y=clamp(points[-1][1]+math.sin(heading)*step,MARGIN,CANVAS_HEIGHT-MARGIN)
                points.append([rnd(x),rnd(y)])
        duration=round(clamp(float(action["duration"])+float(action["hesitation"]),90,1500));family=family_for(action["movementStyle"]);added=[]
        if not action["brushDown"]:
            event={"type":"move","action":"move_tip","timestamp":self.clock,"duration":duration,"from":start,"to":points[-1],"decision":decision_index};self.events.append(event);added.append(event)
            self.clock+=duration;self.position=list(points[-1]);self.memory.consecutiveLowChange+=1;self.physicalActionCount+=1
            return added,{"meaningful":False,"change":0,"family":family,"points":points}
        tip_down={"type":"tip_down","timestamp":self.clock,"point":start,"decision":decision_index};self.events.append(tip_down);added.append(tip_down);self.brushDown=True
        profile=brush_profile(action["brushTool"],float(action["pressure"]))
        stroke={"type":"stroke","action":"erase_path" if action["eraseIntent"] else "draw_path","timestamp":self.clock,"duration":duration,"points":points,"speed":action["speed"],"pressure":action["pressure"],"baseWidth":profile["baseWidth"],"width":profile["width"],"opacity":profile["opacity"],"color":action.get("color") or "#111111","erase":action["eraseIntent"],"family":family,"decision":decision_index,"phase":action["phase"],"layerRole":action["layerRole"],"motifTransform":action["motifTransform"],"branchingDepth":action["branchingDepth"],"strokeCharacter":action["strokeCharacter"],"scale":action["scale"],"brushTool":action["brushTool"],"technique":action["technique"],"motifHint":action.get("motifHint") or "NONE","compositionPass":action.get("compositionPass") or action.get("phase"),"macroIntent":action.get("macroIntent") or ""}
        self.events.append(stroke);added.append(stroke);self.clock+=duration;self.position=list(points[-1]);change=self.memory.remember(points,family,bool(action["eraseIntent"]))
        tip_up={"type":"tip_up","timestamp":self.clock,"point":list(self.position),"decision":decision_index};self.events.append(tip_up);added.append(tip_up);self.brushDown=False
        if float(action["hesitation"])>0:
            pause={"type":"pause","timestamp":self.clock,"duration":action["hesitation"],"point":list(self.position)};self.events.append(pause);added.append(pause)
        self.clock+=float(action["hesitation"]);self.physicalActionCount+=1
        return added,{**change,"family":family,"points":points}
    def lift(self):
        added=[]
        if self.brushDown:
            event={"type":"tip_up","timestamp":self.clock,"point":list(self.position)};self.events.append(event);added.append(event)
        self.brushDown=False
        return added
