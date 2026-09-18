"""Authoritative deterministic canvas mechanics for JPGFLY.

The browser may render these events, but it does not choose or author them.
"""
from __future__ import annotations
import math
from subject_catalog import DRAWABLE_ALIAS_BASE, DRAWABLE_PROGRAMS

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

FIGURE_SHAPES.update({
"HUMAN_FACE":[[0,0],[8,-18],[22,-30],[40,-31],[55,-20],[62,-2],[59,17],[47,31],[29,36],[12,29],[1,14],[0,0],[17,-5],[22,-9],[27,-5],[37,-5],[42,-9],[47,-5],[27,10],[35,13],[44,9]],
"PROFILE_FACE":[[0,0],[9,-20],[24,-31],[39,-28],[45,-17],[55,-12],[46,-5],[52,2],[43,7],[40,21],[29,31],[14,26],[4,14],[0,0],[28,-7],[35,-10],[39,-6],[33,5]],
"FULL_BODY":[[25,-52],[18,-44],[18,-34],[25,-28],[32,-34],[32,-44],[25,-52],[25,-28],[25,2],[12,26],[25,4],[39,27],[25,2],[8,-2],[25,-8],[44,-1]],
"DANCING_FIGURE":[[28,-52],[20,-44],[21,-34],[29,-29],[36,-35],[36,-45],[28,-52],[29,-29],[34,-6],[49,10],[34,-6],[23,14],[34,-6],[11,-18],[33,-10],[54,-27]],
"TWO_FIGURES":[[12,-42],[6,-35],[7,-27],[13,-22],[20,-28],[20,-36],[12,-42],[14,-22],[14,9],[2,29],[14,9],[26,28],[14,9],[42,-20],[42,-42],[35,-49],[27,-44],[27,-34],[35,-27],[42,-31],[42,-20],[42,9],[29,29],[42,9],[55,28]],
"KISSING_FIGURES":[[12,-38],[6,-31],[8,-22],[16,-18],[24,-23],[24,-31],[16,-38],[16,-18],[18,8],[5,28],[18,8],[30,28],[18,8],[33,-19],[30,-30],[36,-38],[45,-37],[51,-29],[48,-20],[40,-16],[33,-19],[40,-16],[40,8],[28,28],[40,8],[53,28]],
"TORSO":[[7,-38],[20,-48],[38,-47],[52,-36],[47,-19],[42,-3],[48,22],[11,22],[17,-2],[12,-19],[7,-38],[20,-20],[30,-15],[40,-20]],
"BODY_CURVE":[[2,-34],[14,-45],[28,-47],[41,-37],[45,-20],[38,-4],[47,14],[41,31],[25,38],[10,30],[4,14],[12,-2],[2,-16]],
"HIPS":[[0,-10],[12,-23],[27,-28],[43,-23],[55,-10],[49,7],[38,20],[27,24],[15,19],[5,8],[0,-10],[14,-1],[27,5],[42,-1]],
"LEGS":[[8,-38],[22,-41],[28,-9],[24,28],[15,48],[8,28],[14,-9],[8,-38],[36,-40],[49,-36],[42,-7],[47,29],[39,48],[31,29],[35,-8],[36,-40]],
"LIPS":[[0,0],[10,-9],[24,-12],[38,-8],[51,0],[39,10],[25,14],[10,9],[0,0],[10,0],[24,3],[39,0],[51,0]],
"TONGUE":[[0,-9],[12,-15],[30,-14],[45,-7],[48,4],[41,18],[27,27],[13,22],[4,11],[0,-9],[23,-9],[24,22]],
"HIGH_HEEL":[[0,0],[9,-24],[20,-17],[32,-10],[51,-6],[57,1],[42,7],[22,5],[16,25],[9,25],[12,4],[0,0]],
"CORSET":[[5,-35],[17,-43],[35,-43],[48,-34],[44,-16],[47,4],[39,27],[14,27],[7,4],[10,-16],[5,-35],[12,-18],[41,-18],[12,-7],[41,-7],[14,5],[39,5]],
"LINGERIE_TOP":[[0,0],[8,-16],[22,-20],[31,-9],[40,-20],[54,-16],[62,0],[49,7],[32,1],[14,7],[0,0],[31,-9],[31,1]],
"UNDERWEAR":[[0,-10],[17,-17],[34,-15],[51,-10],[44,8],[34,23],[25,25],[15,19],[7,7],[0,-10]],
"LOVE_HOTEL_SIGN":[[0,0],[0,-42],[66,-42],[66,0],[0,0],[10,-30],[18,-10],[27,-30],[35,-10],[44,-30],[55,-10]],
"CENSORED_BODY":[[22,-50],[14,-42],[15,-33],[23,-27],[31,-34],[31,-43],[22,-50],[23,-27],[23,17],[10,39],[23,17],[36,39],[23,17],[4,-5],[42,-5],[5,5],[41,5]],
"HEART_LOCK":[[28,32],[4,7],[2,-10],[13,-20],[27,-13],[40,-21],[54,-10],[52,7],[28,32],[21,5],[21,-4],[35,-4],[35,5],[21,5],[28,5],[28,17]],
"ROSE":[[28,0],[20,-10],[24,-23],[36,-26],[46,-18],[45,-6],[36,3],[28,0],[28,0],[18,10],[7,8],[16,17],[10,29],[24,23],[28,42],[32,23],[45,29],[40,16],[52,9],[39,9],[28,0]],
"PERFUME":[[12,0],[12,-27],[38,-27],[38,0],[12,0],[20,-27],[20,-38],[31,-38],[31,-27],[17,-12],[33,-12]],
"COIN":[[0,0],[7,-14],[20,-23],[35,-24],[48,-15],[56,0],[49,15],[35,24],[20,23],[7,14],[0,0],[18,-10],[35,-12],[43,-3],[40,8],[26,13],[15,5],[18,-10]],
"TOKEN_DISK":[[0,0],[8,-16],[23,-25],[40,-24],[54,-13],[60,4],[51,19],[35,27],[18,22],[5,10],[0,0],[18,-8],[40,-8],[40,9],[18,9],[18,-8]],
"CANDLE_CHART":[[0,24],[0,-20],[8,-20],[8,10],[0,10],[0,24],[18,24],[18,-4],[27,-4],[27,19],[18,19],[18,24],[37,24],[37,-31],[46,-31],[46,4],[37,4],[37,24],[57,24],[57,-12],[66,-12],[66,15],[57,15]],
"ROCKET":[[0,22],[8,-10],[28,-38],[46,-11],[52,20],[38,12],[28,25],[16,12],[0,22],[28,-38],[28,-52],[33,-38],[14,15],[5,34],[20,24],[40,14],[53,33],[45,18]],
"BULL_HEAD":[[10,8],[0,-15],[13,-8],[20,-27],[34,-32],[48,-27],[55,-8],[68,-15],[58,8],[48,21],[34,27],[20,21],[10,8],[21,-2],[27,-7],[31,-2],[39,-2],[45,-7],[50,-2],[28,12],[39,12]],
"BEAR_HEAD":[[8,1],[2,-13],[10,-25],[20,-26],[28,-36],[43,-36],[51,-27],[61,-25],[70,-13],[65,2],[54,18],[36,25],[18,18],[8,1],[21,-5],[27,-10],[32,-5],[40,-5],[46,-10],[51,-5],[28,10],[36,14],[44,10]],
"DIAMOND_HAND":[[0,15],[8,-17],[20,-25],[27,-12],[34,-28],[41,-13],[49,-22],[55,-8],[62,-14],[66,2],[54,17],[39,27],[21,29],[0,15],[20,-25],[34,-28],[49,-22]],
"LASER_EYES":[[0,0],[10,-9],[22,-9],[31,0],[22,8],[10,8],[0,0],[31,0],[57,-16],[31,0],[43,0],[53,-9],[65,-9],[74,0],[65,8],[53,8],[43,0],[74,0],[102,-16]],
"MONEY_BAG":[[19,-31],[12,-42],[40,-42],[33,-31],[43,-18],[48,4],[40,24],[12,24],[3,5],[8,-18],[19,-31],[18,-4],[34,-4],[18,7],[34,7],[26,-13],[26,16]],
"RUG":[[0,0],[16,-10],[31,-3],[47,-14],[63,-7],[78,-18],[82,-8],[66,2],[51,-4],[35,7],[19,1],[4,12],[0,0]],
"TERMINAL_SCREEN":[[0,0],[0,-42],[68,-42],[68,0],[0,0],[9,-31],[18,-24],[9,-17],[27,-17],[35,-17],[44,-17],[53,-17]],
"APE_HEAD":[[8,2],[3,-14],[12,-29],[28,-38],[48,-35],[63,-23],[69,-8],[64,9],[50,23],[31,27],[15,18],[8,2],[22,-8],[27,-13],[33,-8],[43,-8],[49,-13],[54,-8],[24,7],[36,13],[51,7]],
"FROG_FACE":[[0,4],[5,-13],[17,-24],[31,-20],[44,-24],[57,-13],[62,4],[55,18],[31,25],[8,18],[0,4],[12,-9],[18,-15],[24,-9],[38,-9],[44,-15],[50,-9],[19,9],[31,14],[44,9]],
"WHALE":[[0,0],[12,-16],[32,-23],[54,-19],[72,-7],[84,1],[72,12],[52,18],[31,20],[12,13],[0,0],[-15,-10],[-28,-22],[-12,-2],[-26,10],[-10,6],[84,1],[97,-8],[91,3],[98,12]],
"SHARK":[[0,0],[15,-13],[37,-18],[55,-11],[72,-3],[86,0],[72,4],[56,13],[34,17],[14,11],[0,0],[36,-18],[47,-34],[54,-14],[37,17],[45,30],[52,14],[86,0],[101,-12],[95,0],[102,12]],
"CAR":[[0,5],[9,-14],[24,-23],[50,-23],[66,-12],[77,-8],[83,5],[0,5],[16,5],[20,14],[30,14],[35,5],[57,5],[61,14],[71,14],[76,5]],
"CAMERA":[[0,0],[0,-33],[61,-33],[61,0],[0,0],[15,-33],[21,-43],[39,-43],[46,-33],[17,-16],[24,-25],[37,-26],[45,-17],[42,-7],[29,-3],[19,-8],[17,-16]],
"GUITAR":[[0,5],[8,-12],[22,-17],[35,-7],[36,9],[25,20],[10,18],[0,5],[30,-5],[51,-28],[57,-24],[35,0],[52,-28],[66,-38]],
"SOFA":[[0,8],[0,-14],[10,-25],[27,-25],[35,-16],[43,-25],[61,-25],[72,-14],[72,8],[0,8],[8,8],[8,20],[17,20],[17,8],[55,8],[55,20],[64,20],[64,8],[17,-7],[55,-7]],
"FRIDGE":[[0,0],[0,-58],[40,-58],[40,0],[0,0],[0,-20],[40,-20],[32,-43],[32,-34],[32,-14],[32,-7]],
"TOILET":[[0,0],[0,-22],[38,-22],[40,-8],[34,1],[34,24],[9,24],[9,4],[0,0],[10,-22],[10,-38],[34,-38],[34,-22]],
"MIRROR":[[0,0],[0,-48],[40,-58],[61,-47],[61,-4],[42,9],[18,9],[0,0],[9,-4],[9,-40],[39,-49],[52,-39],[52,-9],[36,1],[18,1],[9,-4]],
"BANANA":[[0,0],[13,10],[30,11],[47,4],[60,-9],[68,-24],[62,-14],[48,-2],[31,4],[17,3],[5,-5],[0,0]],
"APPLE":[[0,0],[7,-17],[21,-27],[38,-26],[51,-15],[57,1],[51,17],[37,26],[20,25],[7,15],[0,0],[28,-26],[33,-40],[45,-45]],
"MUSHROOM":[[0,0],[8,-18],[24,-28],[42,-28],[58,-17],[65,0],[0,0],[23,0],[20,30],[44,30],[41,0]],
"TREE":[[27,34],[27,5],[16,-7],[9,-22],[18,-17],[27,-7],[27,-28],[17,-42],[28,-35],[35,-49],[40,-32],[53,-40],[45,-20],[57,-13],[42,-12],[34,5],[34,34]],
"MOUNTAIN":[[0,22],[17,-4],[29,-28],[40,-9],[52,-20],[70,4],[88,22],[0,22],[29,-28],[35,-18],[40,-9]],
"CLOUD":[[0,7],[5,-7],[17,-15],[29,-12],[38,-23],[53,-22],[62,-11],[76,-9],[84,3],[80,14],[63,19],[45,18],[31,21],[15,17],[0,7]],
"RAIN_CLOUD":[[0,-5],[6,-18],[18,-25],[31,-22],[39,-32],[54,-30],[63,-20],[77,-18],[85,-6],[80,5],[64,10],[46,8],[30,11],[14,7],[0,-5],[18,14],[12,30],[35,13],[30,32],[53,12],[49,30],[70,9],[67,26]],
"WAVE_ICON":[[0,10],[11,-2],[23,-8],[36,-3],[48,9],[61,12],[73,5],[84,-8],[77,8],[66,18],[52,21],[39,16],[27,7],[17,5],[7,15],[0,10]],
"CITY_BLOCK":[[0,20],[0,-18],[18,-18],[18,20],[18,-35],[38,-35],[38,20],[38,-8],[57,-8],[57,20],[57,-28],[76,-28],[76,20],[0,20]],
"BRIDGE":[[0,20],[0,2],[12,2],[22,-9],[34,-15],[47,-15],[59,-9],[70,2],[83,2],[83,20],[0,20],[12,2],[12,20],[70,2],[70,20],[22,-9],[22,20],[59,-9],[59,20]],
"TOWER":[[0,22],[12,-30],[22,-48],[33,-30],[46,22],[0,22],[10,5],[37,5],[14,-12],[33,-12],[12,-30],[33,-30]]
})

FIGURE_SHAPES.update({
"TOOTH":[[0,0],[6,-18],[17,-31],[31,-35],[45,-31],[56,-18],[60,0],[50,19],[42,38],[31,26],[20,39],[10,20],[0,0]],
"MATING_DANCE":[[0,0],[10,-12],[25,-16],[38,-8],[47,4],[39,15],[24,18],[10,10],[0,0],[24,18],[36,29],[52,28],[64,17],[67,3],[58,-8],[43,-11],[30,-3],[24,18],[24,18],[12,30],[0,29],[-10,19],[-12,7],[-4,-3],[8,-5],[20,3]],
"OOZE":[[0,0],[8,-12],[21,-18],[35,-15],[48,-6],[58,8],[55,21],[47,30],[38,22],[31,35],[23,24],[14,32],[8,19],[0,14],[0,0],[18,-3],[34,-1],[49,6]],
"SLIME":[[0,0],[6,-16],[18,-26],[34,-28],[49,-20],[59,-6],[61,10],[54,22],[47,14],[42,31],[34,19],[26,34],[19,19],[10,25],[4,12],[0,0],[16,-8],[31,-10],[45,-5]]
})

def _alias_variant_shape(alias,base_points):
    seed=sum((i+1)*ord(ch) for i,ch in enumerate(alias))
    sx=.90+((seed%17)/100)
    sy=.90+(((seed//17)%17)/100)
    shear=(((seed//289)%11)-5)/100
    offset=((seed//3179)%7)-3
    return [[round(x*sx+y*shear,3),round(y*sy+offset,3)] for x,y in base_points]

for _alias,_base in DRAWABLE_ALIAS_BASE.items():
    if _base not in FIGURE_SHAPES:
        raise RuntimeError(f"Drawable alias base is missing geometry: {_alias} -> {_base}")
    if _alias not in FIGURE_SHAPES:
        FIGURE_SHAPES[_alias]=_alias_variant_shape(_alias,FIGURE_SHAPES[_base])

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
    profiles={"ink_line":(1,.92),"soft_paint":(2.15,.72),"dry_brush":(1.45,.76),"fine_pen":(.42,.98),"charcoal_grain":(1.35,.78),"wash":(3.1,.62),"stipple":(.78,.92),"splatter":(.7,.88),"subtractive":(1.7,1),"neon_glow":(1.18,.98),"impasto_heavy":(2.65,.98),"oil_lump":(3.0,.94),"chrome_ribbon":(1.85,.96),"airbrush_fog":(3.6,.42),"marker_bleed":(2.15,.74)}
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


SUBJECT_GROUP_BY_MOTIF={
    motif:program
    for program,motifs in DRAWABLE_PROGRAMS.items()
    for motif in motifs
}

def _shape_circle(cx,cy,r,steps=16):
    return [[cx+math.cos(i/steps*math.tau)*r,cy+math.sin(i/steps*math.tau)*r] for i in range(steps+1)]

def _shape_rect(x,y,w,h):
    return [[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]

def _shape_line(*points):
    return [[float(x),float(y)] for x,y in points]

def _semantic_subject_parts(motif):
    """Return disconnected local-coordinate strokes for recognizable subjects."""
    base=DRAWABLE_ALIAS_BASE.get(motif,motif)
    group=SUBJECT_GROUP_BY_MOTIF.get(motif,"")
    contour=FIGURE_SHAPES.get(motif) or FIGURE_SHAPES.get(base)
    if not contour:return None

    # People: disconnected anatomy reads much more clearly than one continuous scribble.
    if group=="PEOPLE_EVERYWHERE" or base in {"FULL_BODY","DANCING_FIGURE","TWO_FIGURES","TORSO","HUMAN_FACE","PROFILE_FACE"}:
        if base in {"HUMAN_FACE","PROFILE_FACE"} or motif.endswith("_FACE"):
            return [
                _shape_circle(28,-8,24,18),
                _shape_circle(20,-13,2.8,8),
                _shape_circle(37,-13,2.8,8),
                _shape_line((20,7),(28,11),(37,7)),
                _shape_line((27,-5),(25,1),(30,2)),
            ]
        if base=="TWO_FIGURES" or any(token in motif for token in ("COUPLE","PAIR","HUGGING")):
            return [
                _shape_circle(16,-34,9,12),_shape_line((16,-25),(16,8)),_shape_line((16,-12),(2,2)),_shape_line((16,-12),(31,0)),_shape_line((16,8),(6,31)),_shape_line((16,8),(27,31)),
                _shape_circle(48,-34,9,12),_shape_line((48,-25),(48,8)),_shape_line((48,-12),(33,0)),_shape_line((48,-12),(62,2)),_shape_line((48,8),(37,31)),_shape_line((48,8),(58,31)),
            ]
        return [
            _shape_circle(28,-35,9,12),
            _shape_line((28,-26),(28,9)),
            _shape_line((28,-12),(8,2)),
            _shape_line((28,-12),(50,1)),
            _shape_line((28,9),(14,35)),
            _shape_line((28,9),(43,35)),
        ]

    if group=="AFTER_DARK_EXTENDED":
        if base in {"LIPS"} or "KISS" in motif:
            return [contour,_shape_line((10,0),(25,3),(40,0))]
        if base in {"MIRROR"}:
            return [contour,_shape_rect(10,-38,35,31),_shape_line((26,-32),(20,-18),(29,-8))]
        if base in {"LINGERIE_TOP","UNDERWEAR","CORSET","LEGS","BODY_CURVE"}:
            return [contour,_shape_line((16,-10),(30,-3),(44,-10)),_shape_line((30,-3),(30,18))]
        return [contour,_shape_circle(27,-5,5,10)]

    if group=="CRYPTO_MARKET":
        if base in {"COIN","TOKEN_DISK","CIRCLE","DIAMOND"}:
            return [_shape_circle(30,0,26,20),_shape_circle(30,0,19,18),_shape_line((23,-10),(36,-10),(39,-3),(21,6),(37,6))]
        if base=="CANDLE_CHART" or any(k in motif for k in ("CHART","CANDLE","BREAKOUT","CRASH","DUMP")):
            return [
                _shape_line((0,26),(0,-34)),_shape_line((0,26),(68,26)),
                _shape_line((14,17),(14,-18)),_shape_rect(9,-8,10,16),
                _shape_line((32,20),(32,-29)),_shape_rect(27,-20,10,23),
                _shape_line((50,10),(50,-12)),_shape_rect(45,-7,10,14),
                _shape_line((7,17),(22,6),(36,9),(53,-15),(67,-24)),
            ]
        if base=="ROCKET":
            return [contour,_shape_circle(29,-15,6,10),_shape_line((19,15),(9,32),(24,24)),_shape_line((39,14),(52,31),(35,23)),_shape_line((27,24),(22,39),(31,31),(38,40))]
        if base in {"BULL_HEAD","BEAR_HEAD","APE_HEAD","FROG_FACE","WHALE","SHARK"}:
            return [contour,_shape_circle(24,-4,2.5,8),_shape_circle(43,-4,2.5,8),_shape_line((26,12),(35,16),(44,12))]
        if base=="TERMINAL_SCREEN":
            return [contour,_shape_line((9,-29),(20,-22),(9,-15)),_shape_line((25,-15),(53,-15)),_shape_line((25,-7),(47,-7))]
        return [contour,_shape_circle(28,0,7,10)]

    if group=="TECH_AND_INTERNET":
        if motif in {"LAPTOP","KEYBOARD"}:
            return [_shape_rect(5,-36,58,36),_shape_line((0,4),(68,4),(58,14),(10,14),(0,4)),_shape_line((14,9),(54,9))]
        if motif in {"SMARTPHONE","TABLET","TV_REMOTE"} or base=="PHONE":
            return [_shape_rect(12,-42,32,60),_shape_rect(16,-35,24,43),_shape_circle(28,12,2.5,8)]
        if motif in {"DESKTOP_MONITOR","CODE_WINDOW","COMMAND_PROMPT","CHAT_WINDOW","SERVER_RACK"} or base in {"TV","TERMINAL_SCREEN"}:
            return [_shape_rect(0,-38,66,42),_shape_rect(6,-31,54,27),_shape_line((13,-22),(22,-15),(13,-8)),_shape_line((29,-8),(50,-8))]
        if motif in {"HEADPHONES"}:
            return [_shape_circle(30,0,25,18),_shape_rect(3,-2,8,18),_shape_rect(49,-2,8,18)]
        return [contour,_shape_rect(10,-18,32,18)]

    if group=="HOME_AND_OBJECTS":
        if base=="CUP":
            return [_shape_rect(8,-24,32,30),_shape_circle(42,-9,9,12),_shape_line((13,-30),(17,-38)),_shape_line((25,-30),(29,-40))]
        if base in {"CHAIR","TABLE"}:
            return [contour,_shape_line((10,0),(10,28)),_shape_line((44,0),(44,28))]
        if base in {"LAMP","CLOCK","BOTTLE","KEY","BED","FRIDGE","TOILET","MIRROR"}:
            return [contour,_shape_line((12,-8),(42,-8)),_shape_circle(27,-18,3,8)]
        return [contour,_shape_line((12,-4),(28,3),(44,-4))]

    if group=="FOOD_AND_DRINK":
        if "PIZZA" in motif:
            return [_shape_line((0,24),(32,-32),(64,24),(0,24)),_shape_circle(26,-2,3,8),_shape_circle(42,7,3,8),_shape_circle(31,14,3,8)]
        if "BURGER" in motif:
            return [_shape_line((5,-8),(15,-20),(48,-20),(59,-8)),_shape_line((5,-8),(59,-8)),_shape_line((7,2),(57,2)),_shape_line((10,14),(54,14)),_shape_line((15,25),(49,25))]
        if "DONUT" in motif:
            return [_shape_circle(30,0,25,18),_shape_circle(30,0,10,14)]
        if base=="CUP":
            return [_shape_rect(7,-24,34,31),_shape_circle(43,-9,9,12)]
        return [contour,_shape_circle(27,0,3,8),_shape_line((15,10),(39,10))]

    if group=="ANIMALS_AND_WILDLIFE":
        if base in {"CAT_FACE","DOG_FACE","RABBIT_HEAD","BEAR_HEAD","APE_HEAD","FROG_FACE","BIRD_HEAD"}:
            return [contour,_shape_circle(21,-3,2.5,8),_shape_circle(41,-3,2.5,8),_shape_line((25,11),(31,15),(38,11))]
        if base in {"FISH","WHALE","SHARK"}:
            return [contour,_shape_circle(42,-4,2.5,8),_shape_line((18,0),(32,0))]
        return [contour,_shape_circle(26,0,3,8),_shape_line((14,10),(38,10))]

    if group=="NATURE_AND_WEATHER":
        if base=="TREE":
            return [_shape_line((28,34),(28,-18)),_shape_line((28,-8),(12,-26)),_shape_line((28,-12),(44,-31)),_shape_circle(11,-31,12,12),_shape_circle(31,-39,15,14),_shape_circle(50,-30,12,12)]
        if base in {"MOUNTAIN"}:
            return [contour,_shape_line((29,-28),(35,-18),(40,-9)),_shape_line((52,-20),(57,-10))]
        if base in {"CLOUD","RAIN_CLOUD"}:
            return [contour,_shape_line((20,18),(15,34)),_shape_line((40,17),(35,34)),_shape_line((61,14),(57,31))]
        return [contour,_shape_line((10,14),(46,14))]

    if group=="TRANSPORT_AND_CITY":
        if base=="CAR":
            return [
                _shape_line((0,8),(8,-10),(24,-20),(51,-20),(67,-9),(79,-4),(84,8),(0,8)),
                _shape_circle(20,10,8,14),_shape_circle(65,10,8,14),
                _shape_line((24,-20),(30,-7),(54,-7),(51,-20)),
            ]
        if motif in {"AIRPLANE","HELICOPTER"} or base=="ROCKET":
            return [contour,_shape_line((25,-5),(0,9)),_shape_line((25,-5),(52,10)),_shape_line((40,-12),(54,-22))]
        if any(k in motif for k in ("BOAT","SHIP","SUBMARINE")):
            return [_shape_line((0,7),(60,7),(50,20),(12,20),(0,7)),_shape_line((28,7),(28,-25)),_shape_line((28,-24),(47,-7),(28,-7))]
        if base in {"CITY_BLOCK","TOWER","HOUSE","BRIDGE"}:
            return [contour,_shape_rect(12,-12,10,12),_shape_rect(32,-12,10,12)]
        return [contour,_shape_line((12,-8),(42,-8))]

    if group=="FASHION_AND_STYLE":
        if base in {"TORSO","BODY_CURVE"}:
            return [contour,_shape_line((15,-18),(28,-8),(42,-18)),_shape_line((28,-8),(28,20))]
        if base=="HIGH_HEEL":
            return [contour,_shape_line((17,5),(12,28)),_shape_line((12,28),(20,28))]
        if motif in {"SUNGLASSES","GLASSES"}:
            return [_shape_circle(18,0,10,12),_shape_circle(43,0,10,12),_shape_line((28,0),(33,0)),_shape_line((8,0),(-2,-5)),_shape_line((53,0),(63,-5))]
        return [contour,_shape_line((12,0),(45,0))]

    if group=="MUSIC_AND_MEDIA":
        if base=="GUITAR":
            return [_shape_circle(20,4,16,16),_shape_circle(29,-8,13,14),_shape_line((35,-17),(67,-48)),_shape_line((39,-13),(71,-44)),_shape_line((26,-4),(58,-35))]
        if motif in {"VINYL_RECORD","CD_DISC","DISCO_BALL"}:
            return [_shape_circle(30,0,26,20),_shape_circle(30,0,7,12)]
        if base=="CAMERA":
            return [contour,_shape_circle(31,-16,12,16),_shape_circle(31,-16,4,10)]
        return [contour,_shape_line((10,-7),(42,-7))]

    if group=="SIGNS_AND_SYMBOLS":
        if "HEART" in motif or base=="HEART":
            if "BROKEN" in motif:
                return [contour,_shape_line((30,-18),(24,-5),(33,3),(26,17))]
            if "ARROW" in motif:
                return [contour,_shape_line((4,18),(52,-22)),_shape_line((52,-22),(43,-21),(50,-13))]
            return [contour,_shape_circle(18,-12,3,8)]
        if "TARGET" in motif:
            return [_shape_circle(30,0,26,18),_shape_circle(30,0,16,16),_shape_circle(30,0,6,12)]
        if "WARNING" in motif or base=="TRIANGLE":
            return [contour,_shape_line((31,-15),(31,7)),_shape_circle(31,15,2,8)]
        return [contour,_shape_line((12,0),(44,0))]

    # Original explicit motifs still gain disconnected details where possible.
    if base in {"HUMAN_FACE","WEIRD_FACE","MASK","CAT_FACE","DOG_FACE","RABBIT_HEAD","BEAR_HEAD","APE_HEAD","FROG_FACE"}:
        return [contour,_shape_circle(20,-4,2.5,8),_shape_circle(40,-4,2.5,8),_shape_line((24,12),(31,16),(39,12))]
    if base in {"CAR","CAMERA","GUITAR","TERMINAL_SCREEN","COIN","TOKEN_DISK"}:
        return [contour,_shape_circle(28,0,6,10)]
    return [contour]

def compound_figurative_parts(motif,start,heading,movement_distance):
    local_parts=_semantic_subject_parts(motif)
    if not local_parts:return None
    flat=[point for part in local_parts for point in part]
    xs=[p[0] for p in flat];ys=[p[1] for p in flat]
    span=max(max(xs)-min(xs),max(ys)-min(ys),1)
    target_span=clamp(float(movement_distance)*1.18,48,145)
    physical_scale=clamp(target_span/span,.62,2.15)
    parts=[]
    for part in local_parts:
        if len(part)<2:continue
        rotated=[]
        for point in part:
            x,y=rotate_point(point,heading,physical_scale,start)
            rotated.append([rnd(clamp(x,MARGIN,CANVAS_WIDTH-MARGIN)),rnd(clamp(y,MARGIN,CANVAS_HEIGHT-MARGIN))])
        parts.append(rotated)
    return parts

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
    def remember(self,points,family,erase=False,count_family=True):
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
        self.intersections+=new_intersections
        if count_family:self.familyCounts[family]=self.familyCounts.get(family,0)+1
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
        coverage=(occupied/total) if total else 0
        local_density=(self.grid[current_cell]/max_density) if max_density else 0
        sorted_regions=sorted(region_density,reverse=True)
        top_region=sorted_regions[0] if sorted_regions else 0
        second_region=sorted_regions[1] if len(sorted_regions)>1 else 0
        focal_commitment=clamp(top_region-second_region,0,1)
        region_sum=sum(region_density) or 1
        focus_strength=clamp((top_region/region_sum)*3.2,0,1)
        empty_regions=sum(1 for value in region_density if value<.12)/12
        empty_space_balance=clamp(1-abs(empty_regions-.46)/.46,0,1)
        hierarchy_strength=clamp(focal_commitment*.58+regional_contrast*.42,0,1)
        edge_indices=(0,1,2,3,4,7,8,9,10,11)
        edge_pressure=clamp(sum(region_density[i] for i in edge_indices)/(region_sum or 1),0,1)
        low_change=clamp(self.consecutiveLowChange/12,0,1)
        overwork_risk=clamp(coverage*.34+repetition*.28+local_density*.18+low_change*.20,0,1)
        revision_potential=clamp(overwork_risk*.52+repetition*.20+regional_contrast*.12+low_change*.16,0,1)
        return {"currentForelegPosition":list(current_position),"canvasOccupancy":rnd(coverage),"negativeSpace":self.negative_space(current_position),"focalArea":self.focal_point(),"nearbyLines":self.nearby(current_position),"intersections":self.intersections,"densityPeak":max_density,"densityBalance":rnd(1-abs(left-right)/occupied) if occupied else 1,"repetition":rnd(repetition),"recentMarks":[path[-3:] for path in self.paths[-4:]],"visitedAreas":self.visits[-48:],"familyCounts":dict(self.familyCounts),"meaningfulChangeRate":rnd(self.meaningfulChanges/len(self.paths)) if self.paths else 1,"consecutiveLowChange":self.consecutiveLowChange,"elapsedDrawingTime":elapsed,"decisionCount":decision_count,"physicalActionCount":physical_action_count,"quadrantDensity":[rnd(v/quadrant_max) for v in quadrants],"regionDensity":region_density,"regionDensityGrid12":region_density,"occupiedRegions":occupied_regions,"regionalContrast":regional_contrast,"densityContrast":rnd(contrast),"localDensity":rnd(local_density),"dominantDirection":rnd((dominant_bin+.5)/len(self.directionBins)*math.tau),"directionalUniformity":rnd(max(self.directionBins)/direction_total) if direction_total else 0,"lastCompositionalChange":self.lastChange,"focusStrength":rnd(focus_strength),"emptySpaceBalance":rnd(empty_space_balance),"hierarchyStrength":rnd(hierarchy_strength),"edgePressure":rnd(edge_pressure),"focalCommitment":rnd(focal_commitment),"overworkRisk":rnd(overwork_risk),"revisionPotential":rnd(revision_potential)}


class ServerCanvasMechanics:
    def __init__(self,seed,session_id):
        self.seed=int(seed)&0xffffffff;self.events=[{"type":"session_start","sessionId":session_id,"timestamp":0},{"type":"clear","timestamp":20}]
        self.memory=CanvasMemory();self.position=[735.0,48.0];self.brushDown=False;self.clock=100;self.physicalActionCount=0
    def observe(self,decision_count):return self.memory.observe(self.position,self.clock,decision_count,self.physicalActionCount)
    def execute(self,action,decision_index):
        start=list(self.position)
        count=int(clamp(round(18+float(action["movementDistance"])/2.7+int(action.get("branchingDepth") or 0)*4),18,96))
        motif=action.get("motifHint")
        use_subject=bool(action.get("brushDown") and not action.get("eraseIntent") and motif in FIGURE_MOTIFS)
        compound=compound_figurative_parts(motif,start,float(action["targetDirection"]),float(action["movementDistance"])) if use_subject else None
        figure=None if compound else (figurative_primitive(motif,start,float(action["targetDirection"]),float(action["movementDistance"])) if use_subject else None)
        points=figure or [start]

        if figure is None and compound is None:
            step=float(action["movementDistance"])/(count-1);heading=float(action["targetDirection"])
            for i in range(1,count):
                t=i/(count-1)
                heading+=float(action["curvature"])/(count-1)+(style_offset(action["movementStyle"],t,i)+motif_offset(motif,t,i)*3.2)/(count-1)
                x=points[-1][0]+math.cos(heading)*step;y=points[-1][1]+math.sin(heading)*step
                if x<MARGIN or x>CANVAS_WIDTH-MARGIN:heading=math.pi-heading
                if y<MARGIN or y>CANVAS_HEIGHT-MARGIN:heading=-heading
                x=clamp(points[-1][0]+math.cos(heading)*step,MARGIN,CANVAS_WIDTH-MARGIN)
                y=clamp(points[-1][1]+math.sin(heading)*step,MARGIN,CANVAS_HEIGHT-MARGIN)
                points.append([rnd(x),rnd(y)])

        duration=round(clamp(float(action["duration"])+float(action["hesitation"]),90,1500))
        family=family_for(action["movementStyle"])
        added=[]

        if not action["brushDown"]:
            event={"type":"move","action":"move_tip","timestamp":self.clock,"duration":duration,"from":start,"to":points[-1],"decision":decision_index}
            self.events.append(event);added.append(event)
            self.clock+=duration;self.position=list(points[-1]);self.memory.consecutiveLowChange+=1;self.physicalActionCount+=1
            return added,{"meaningful":False,"change":0,"family":family,"points":points}

        profile=brush_profile(action["brushTool"],float(action["pressure"]))

        if compound:
            aggregate={"meaningful":False,"change":0.0,"newCells":0,"newIntersections":0,"length":0.0}
            all_points=[]
            cursor=list(self.position)
            part_duration=max(90,round(duration/max(1,len(compound))))
            for part_index,part in enumerate(compound[:14]):
                if len(part)<2:continue
                part_start=list(part[0])
                travel=distance(cursor,part_start)
                if travel>1.5:
                    move_duration=round(clamp(70+travel*1.25,80,360))
                    move={"type":"move","action":"move_tip","timestamp":self.clock,"duration":move_duration,"from":list(cursor),"to":part_start,"decision":decision_index,"compoundSubject":motif,"subjectPart":part_index}
                    self.events.append(move);added.append(move);self.clock+=move_duration
                tip_down={"type":"tip_down","timestamp":self.clock,"point":part_start,"decision":decision_index,"compoundSubject":motif,"subjectPart":part_index}
                self.events.append(tip_down);added.append(tip_down);self.brushDown=True
                stroke={"type":"stroke","action":"draw_path","timestamp":self.clock,"duration":part_duration,"points":part,"speed":action["speed"],"pressure":action["pressure"],"baseWidth":profile["baseWidth"],"width":profile["width"],"opacity":profile["opacity"],"color":action.get("color") or "#111111","erase":False,"family":family,"decision":decision_index,"phase":action["phase"],"layerRole":action["layerRole"],"motifTransform":action["motifTransform"],"branchingDepth":action["branchingDepth"],"strokeCharacter":action["strokeCharacter"],"scale":action["scale"],"brushTool":action["brushTool"],"technique":action["technique"],"motifHint":motif or "NONE","compositionPass":action.get("compositionPass") or action.get("phase"),"macroIntent":action.get("macroIntent") or "","paletteName":action.get("paletteName") or "","materialStyle":action.get("materialStyle") or "ink_line","renderEffect":action.get("renderEffect") or "MATTE","paintDepth":float(action.get("paintDepth") or .08),"compoundSubject":True,"subjectPart":part_index,"subjectPartCount":len(compound)}
                self.events.append(stroke);added.append(stroke);self.clock+=part_duration
                change=self.memory.remember(part,family,False,count_family=(part_index==0))
                aggregate["meaningful"]=aggregate["meaningful"] or bool(change.get("meaningful"))
                for key in ("change","newCells","newIntersections","length"):
                    aggregate[key]+=float(change.get(key,0) or 0)
                cursor=list(part[-1]);self.position=list(cursor);all_points.extend(part)
                tip_up={"type":"tip_up","timestamp":self.clock,"point":list(cursor),"decision":decision_index,"compoundSubject":motif,"subjectPart":part_index}
                self.events.append(tip_up);added.append(tip_up);self.brushDown=False

            if float(action["hesitation"])>0:
                pause={"type":"pause","timestamp":self.clock,"duration":action["hesitation"],"point":list(self.position)}
                self.events.append(pause);added.append(pause);self.clock+=float(action["hesitation"])
            self.physicalActionCount+=1
            aggregate["change"]=rnd(aggregate["change"])
            aggregate["length"]=rnd(aggregate["length"])
            return added,{**aggregate,"family":family,"points":all_points,"compoundSubject":motif,"subjectParts":len(compound)}

        tip_down={"type":"tip_down","timestamp":self.clock,"point":start,"decision":decision_index}
        self.events.append(tip_down);added.append(tip_down);self.brushDown=True
        stroke={"type":"stroke","action":"erase_path" if action["eraseIntent"] else "draw_path","timestamp":self.clock,"duration":duration,"points":points,"speed":action["speed"],"pressure":action["pressure"],"baseWidth":profile["baseWidth"],"width":profile["width"],"opacity":profile["opacity"],"color":action.get("color") or "#111111","erase":action["eraseIntent"],"family":family,"decision":decision_index,"phase":action["phase"],"layerRole":action["layerRole"],"motifTransform":action["motifTransform"],"branchingDepth":action["branchingDepth"],"strokeCharacter":action["strokeCharacter"],"scale":action["scale"],"brushTool":action["brushTool"],"technique":action["technique"],"motifHint":motif or "NONE","compositionPass":action.get("compositionPass") or action.get("phase"),"macroIntent":action.get("macroIntent") or "","paletteName":action.get("paletteName") or "","materialStyle":action.get("materialStyle") or "ink_line","renderEffect":action.get("renderEffect") or "MATTE","paintDepth":float(action.get("paintDepth") or .08)}
        self.events.append(stroke);added.append(stroke);self.clock+=duration;self.position=list(points[-1])
        change=self.memory.remember(points,family,bool(action["eraseIntent"]))
        tip_up={"type":"tip_up","timestamp":self.clock,"point":list(self.position),"decision":decision_index}
        self.events.append(tip_up);added.append(tip_up);self.brushDown=False
        if float(action["hesitation"])>0:
            pause={"type":"pause","timestamp":self.clock,"duration":action["hesitation"],"point":list(self.position)}
            self.events.append(pause);added.append(pause)
        self.clock+=float(action["hesitation"]);self.physicalActionCount+=1
        return added,{**change,"family":family,"points":points}

    def lift(self):
        added=[]
        if self.brushDown:
            event={"type":"tip_up","timestamp":self.clock,"point":list(self.position)};self.events.append(event);added.append(event)
        self.brushDown=False
        return added
