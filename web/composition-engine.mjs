// Mechanical canvas/foreleg layer. It never chooses composition or prepares paths.
// A fly-brain action is converted into one small, deterministic physical movement.
export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 500;
const MARGIN = 24;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const round = (value, places = 3) => Number(value.toFixed(places));
const FIGURE_MOTIFS=new Set(["FLY","CAT_FACE","FISH","TV","GHOST","SNAIL","DUCK","MOUSE","SPIDER","MOTH","BEETLE","BIRD_HEAD","PHONE","KEY","CLOCK","EYEBALL","BOTTLE","WINDOW","LAMP","MASK"]);

function distance(a, b) { return Math.hypot(b[0] - a[0], b[1] - a[1]); }
function orientation(a, b, c) { return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]); }
function intersects(a, b, c, d) {
  return orientation(a, b, c) * orientation(a, b, d) < 0 && orientation(c, d, a) * orientation(c, d, b) < 0;
}

export class CanvasMemory {
  constructor(columns = 16, rows = 10) {
    this.columns = columns;
    this.rows = rows;
    this.grid = new Uint16Array(columns * rows);
    this.segments = [];
    this.paths = [];
    this.visits = [];
    this.intersections = 0;
    this.drawnLength = 0;
    this.erasedLength = 0;
    this.meaningfulChanges = 0;
    this.consecutiveLowChange = 0;
    this.familyCounts = Object.create(null);
    this.focalAreas = [];
    this.directionBins = new Uint32Array(12);
    this.lastChange = 0;
  }

  cell(point) {
    const column = clamp(Math.floor(point[0] / CANVAS_WIDTH * this.columns), 0, this.columns - 1);
    const row = clamp(Math.floor(point[1] / CANVAS_HEIGHT * this.rows), 0, this.rows - 1);
    return {column, row, index: row * this.columns + column};
  }

  cellCenter(index) {
    const column = index % this.columns;
    const row = Math.floor(index / this.columns);
    return [(column + .5) / this.columns * CANVAS_WIDTH, (row + .5) / this.rows * CANVAS_HEIGHT];
  }

  negativeSpace(from = [CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2]) {
    const minimum = Math.min(...this.grid);
    const candidates = [...this.grid.keys()].filter((index) => this.grid[index] === minimum);
    let best = candidates[0] || 0;
    for (const index of candidates) if (distance(from, this.cellCenter(index)) > distance(from, this.cellCenter(best))) best = index;
    return this.cellCenter(best);
  }

  focalPoint() {
    if (!this.focalAreas.length) return [CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2];
    return [...this.focalAreas.reduce((best, item) => item.weight > best.weight ? item : best).point];
  }

  nearby(point, radius = 76) {
    return this.paths.slice(-32).filter((path) => path.some((other) => distance(point, other) <= radius)).length;
  }

  remember(points, family, erase = false) {
    const visitedBefore = new Set();
    let newCells = 0;
    let newIntersections = 0;
    let length = 0;
    for (const point of points) {
      const {index} = this.cell(point);
      if (!visitedBefore.has(index) && this.grid[index] === 0) newCells += 1;
      visitedBefore.add(index);
      if (!erase) this.grid[index] += 1;
    }
    for (let i = 1; i < points.length; i += 1) {
      const segment = [points[i - 1], points[i]];
      length += distance(...segment);
      if (!erase) {
        const angle = (Math.atan2(segment[1][1] - segment[0][1], segment[1][0] - segment[0][0]) + Math.PI * 2) % (Math.PI * 2);
        this.directionBins[Math.floor(angle / (Math.PI * 2) * this.directionBins.length) % this.directionBins.length] += 1;
        for (let j = Math.max(0, this.segments.length - 650); j < this.segments.length; j += 3) {
          if (intersects(...segment, ...this.segments[j])) newIntersections += 1;
        }
        this.segments.push(segment);
      }
    }
    if (erase) this.erasedLength += length;
    else this.drawnLength += length;
    this.intersections += newIntersections;
    this.familyCounts[family] = (this.familyCounts[family] || 0) + 1;
    this.paths.push(points.map((point) => [...point]));
    this.visits.push([...points.at(-1)]);
    const midpoint = points[Math.floor(points.length / 2)];
    this.focalAreas.push({point: [...midpoint], weight: length + newIntersections * 18});
    this.focalAreas = this.focalAreas.sort((a, b) => b.weight - a.weight).slice(0, 12);
    const change = newCells * 1.8 + newIntersections * 1.25 + Math.min(2, length / 65) + (erase ? .5 : 0);
    const meaningful = change >= 1.35;
    this.lastChange = round(change);
    if (meaningful) {
      this.meaningfulChanges += 1;
      this.consecutiveLowChange = 0;
    } else this.consecutiveLowChange += 1;
    return {meaningful, change: round(change), newCells, newIntersections, length: round(length)};
  }

  observe(currentPosition, elapsed, decisionCount, physicalActionCount) {
    const occupied = [...this.grid].filter(Boolean).length;
    const total = this.grid.length;
    const left = [...this.grid].filter((value, i) => value && i % this.columns < this.columns / 2).length;
    const right = occupied - left;
    const maxDensity = Math.max(0, ...this.grid);
    const familyTotal = Object.values(this.familyCounts).reduce((sum, value) => sum + value, 0);
    const repetition = familyTotal ? Math.max(0, ...Object.values(this.familyCounts)) / familyTotal : 0;
    const quadrants = [0, 0, 0, 0];
    for (let index = 0; index < this.grid.length; index += 1) {
      const column = index % this.columns, row = Math.floor(index / this.columns);
      quadrants[(row >= this.rows / 2 ? 2 : 0) + (column >= this.columns / 2 ? 1 : 0)] += this.grid[index];
    }
    const quadrantMax = Math.max(1, ...quadrants), quadrantMean = quadrants.reduce((a, b) => a + b, 0) / 4;
    const densityContrast = Math.sqrt(quadrants.reduce((sum, value) => sum + (value - quadrantMean) ** 2, 0) / 4) / quadrantMax;
    const directionTotal = [...this.directionBins].reduce((sum, value) => sum + value, 0);
    const dominantBin = [...this.directionBins].indexOf(Math.max(...this.directionBins));
    const currentCell = this.cell(currentPosition).index;
    return {
      currentForelegPosition: [...currentPosition], canvasOccupancy: round(occupied / total),
      negativeSpace: this.negativeSpace(currentPosition), focalArea: this.focalPoint(), nearbyLines: this.nearby(currentPosition),
      intersections: this.intersections, densityPeak: maxDensity,
      densityBalance: occupied ? round(1 - Math.abs(left - right) / occupied) : 1,
      repetition: round(repetition), recentMarks: this.paths.slice(-4).map((path) => path.slice(-3)),
      visitedAreas: this.visits.slice(-12), familyCounts: {...this.familyCounts},
      meaningfulChangeRate: this.paths.length ? round(this.meaningfulChanges / this.paths.length) : 1,
      consecutiveLowChange: this.consecutiveLowChange, elapsedDrawingTime: elapsed,
      decisionCount, physicalActionCount, quadrantDensity: quadrants.map(value => round(value / quadrantMax)),
      densityContrast: round(densityContrast), localDensity: maxDensity ? round(this.grid[currentCell] / maxDensity) : 0,
      dominantDirection: round((dominantBin + .5) / this.directionBins.length * Math.PI * 2),
      directionalUniformity: directionTotal ? round(Math.max(...this.directionBins) / directionTotal) : 0,
      lastCompositionalChange: this.lastChange,
    };
  }
}

function styleOffset(style, t, index) {
  switch (style) {
    case "loop": return 5.3 + Math.sin(t * Math.PI * 4) * 2.8;
    case "spiral": return 2.8 + t * 6.4 + Math.sin(t * Math.PI * 6) * 1.4;
    case "jitter": return (index % 2 ? 1 : -1) * (5.4 + t * 3.1);
    case "segmented": return index % 3 === 0 ? 7.2 : -2.8;
    case "branch": return (t > .52 ? -4.8 : 3.6) * Math.sin(t * Math.PI * 2);
    case "cross": return Math.sin(t * Math.PI * 4) * 10.5;
    case "echo": return 1.4 + Math.sin(t * Math.PI * 6) * 3.8;
    case "cluster": return 4.4 + Math.sin(t * Math.PI * 10) * 5.6;
    case "contour": return 1.2 + Math.sin(t * Math.PI * 5) * 2.7;
    case "knot": return 4.8 + Math.sin(t * Math.PI * 8) * 6.2;
    case "fracture": return index % 4 < 2 ? 8.4 : -7.1;
    case "orbit": return 6.1 + Math.sin(t * Math.PI * 3) * 2.4;
    case "web": return Math.sin(t * Math.PI * 12) * 8.8 + (index % 5 === 0 ? 5 : -1.2);
    case "coil": return 5.7 + t * 5.2 + Math.sin(t * Math.PI * 10) * 2.2;
    case "petal": return Math.sin(t * Math.PI * 4) * 7.4 + Math.cos(t * Math.PI * 2) * 2.4;
    case "lattice": return index % 4 === 0 ? 9.2 : index % 2 ? -4.8 : 3.6;
    case "hook": return t < .58 ? .7 : 9.8 * Math.sin((t - .58) / .42 * Math.PI);
    case "starburst": return index % 5 === 0 ? 12.4 : -2.9;
    case "accent": return Math.sin(t * Math.PI) * .22;
    case "bold": return Math.sin(t * Math.PI) * .34;
    case "sweep": return Math.sin(t * Math.PI) * .72;
    default: return 0;
  }
}

function motifOffset(motif,t,index) {
  switch (motif || 'NONE') {
    case 'BANANA_CURVE': return Math.sin(t*Math.PI)*1.45;
    case 'PHALLIC_SPIRAL': return t<.55 ? .08 : 2.9 + Math.sin((t-.55)/.45*Math.PI*4)*1.15;
    case 'PAIRED_FLIES': return Math.sin(t*Math.PI*4)*2.25;
    case 'MATING_DANCE': return Math.sin(t*Math.PI*6)*2.65 + Math.sin(t*Math.PI*2)*.75;
    case 'WEIRD_FACE': return Math.sin(t*Math.PI*4)*2.4 + Math.cos(t*Math.PI*2)*.8;
    case 'UNDERWEAR': return index%4<2 ? 1.2 : -1.2;
    case 'CROWN': return index%3===0 ? 2.25 : -1.05;
    case 'CENSORED_MARK': return 0;
    case 'SLIME': return Math.sin(t*Math.PI*7)*1.55 + (t>.7 ? 1.1 : 0);
    case 'MEAT_BLOB': return Math.sin(t*Math.PI*5)*2.0 + Math.cos(t*Math.PI*3)*1.0;
    case 'OOZE': return Math.sin(t*Math.PI*8)*1.15 + t*1.2;
    case 'EYE': return Math.sin(t*Math.PI*4)*1.75;
    case 'WING': return Math.sin(t*Math.PI*3)*1.35;
    case 'TOOTH': return index%3===0 ? 1.65 : -.55;
    case 'FLOWER': return Math.sin(t*Math.PI*6)*1.8;
    case 'BONE': return index%5===0 ? 1.3 : -.25;
    case 'CHAIR': return index%4===0 ? 1.5 : 0;
    case 'SHOE': return t>.55 ? 1.5*Math.sin((t-.55)/.45*Math.PI) : .2;
    case 'TRASH': return Math.sin(index*2.13)*1.3;
    default: return 0;
  }
}

function rotatePoint(point,angle,scale,start){
  const x=point[0]*scale,y=point[1]*scale,cs=Math.cos(angle),sn=Math.sin(angle);
  return [clamp(round(start[0]+x*cs-y*sn),MARGIN,CANVAS_WIDTH-MARGIN),clamp(round(start[1]+x*sn+y*cs),MARGIN,CANVAS_HEIGHT-MARGIN)];
}

function figurativePrimitive(motif,start,heading,distance){
  const size=clamp(distance/90,.62,1.55);
  const shapes={
    FLY:[[0,0],[10,-8],[20,-5],[28,0],[20,5],[10,8],[0,0],[-10,-13],[-24,-18],[-18,-4],[0,0],[-10,13],[-24,18],[-18,4],[0,0],[18,-14],[30,-18],[23,-3],[0,0],[18,14],[30,18],[23,3],[0,0],[34,0]],
    CAT_FACE:[[0,0],[8,-13],[16,-5],[28,-12],[40,-5],[48,-13],[56,0],[58,18],[50,31],[38,38],[20,38],[7,31],[0,18],[0,0],[14,13],[19,9],[24,13],[29,9],[34,13],[41,18],[34,22],[28,18],[23,23],[17,18],[9,21],[0,20],[-10,18]],
    FISH:[[0,0],[12,-12],[28,-18],[45,-14],[58,0],[45,14],[28,18],[12,12],[0,0],[-17,-14],[-12,0],[-17,14],[0,0],[42,0],[47,-3],[50,0],[47,3],[42,0]],
    TV:[[0,0],[0,-30],[48,-30],[48,6],[0,6],[0,0],[12,-5],[36,-5],[36,-21],[12,-21],[12,-5],[24,-30],[17,-42],[24,-30],[32,-43],[24,-30]],
    GHOST:[[0,0],[0,-20],[7,-34],[18,-41],[31,-39],[41,-29],[46,-13],[44,7],[36,1],[29,8],[22,1],[15,8],[8,1],[0,7],[0,0],[13,-18],[17,-22],[21,-18],[29,-18],[33,-22],[37,-18]],
    SNAIL:[[0,0],[14,-5],[28,-5],[40,0],[48,7],[53,7],[57,3],[60,7],[53,7],[45,14],[30,17],[15,15],[0,9],[0,0],[16,5],[28,1],[35,7],[31,13],[21,14],[14,9],[16,5]],
    DUCK:[[0,0],[12,-10],[27,-12],[38,-6],[46,-11],[56,-9],[48,-3],[57,2],[46,4],[39,12],[25,17],[10,15],[0,8],[0,0],[33,-8],[35,-13],[38,-8]],
    MOUSE:[[0,0],[7,-14],[16,-20],[24,-14],[31,-21],[40,-15],[47,-4],[48,10],[42,22],[31,29],[18,28],[7,21],[0,10],[0,0],[13,4],[18,0],[23,4],[30,3],[35,0],[40,3],[47,8],[58,7],[66,2]],
    SPIDER:[[0,0],[12,-8],[24,0],[12,8],[0,0],[-12,-14],[-26,-19],[-12,-4],[0,0],[-16,0],[-30,-3],[0,0],[-12,14],[-26,19],[0,4],[24,0],[36,-15],[24,0],[38,0],[24,0],[36,15]],
    MOTH:[[0,0],[12,-8],[25,-20],[39,-13],[31,-1],[18,4],[31,9],[39,21],[25,25],[12,12],[0,0],[-12,-8],[-25,-20],[-39,-13],[-31,-1],[-18,4],[-31,9],[-39,21],[-25,25],[-12,12],[0,0]],
    BEETLE:[[0,0],[10,-13],[24,-18],[38,-12],[46,0],[38,12],[24,18],[10,13],[0,0],[23,0],[46,0],[23,0],[11,-18],[1,-27],[11,-18],[35,-18],[45,-27],[35,-18],[11,18],[1,27],[11,18],[35,18],[45,27]],
    BIRD_HEAD:[[0,0],[10,-15],[25,-23],[40,-18],[51,-7],[61,-4],[51,1],[40,4],[36,16],[24,24],[10,19],[0,8],[0,0],[34,-10],[38,-13],[42,-10],[38,-7],[34,-10]],
    PHONE:[[0,0],[0,-35],[28,-35],[28,10],[0,10],[0,0],[6,-29],[22,-29],[22,2],[6,2],[6,-29],[14,6],[16,6]],
    KEY:[[0,0],[10,-10],[21,-10],[31,0],[21,10],[10,10],[0,0],[31,0],[55,0],[55,7],[63,7],[63,0],[70,0]],
    CLOCK:[[0,0],[8,-14],[23,-21],[39,-17],[49,-5],[51,11],[44,25],[30,33],[14,30],[2,19],[0,0],[25,5],[25,-10],[25,5],[37,13]],
    EYEBALL:[[0,0],[12,-10],[28,-15],[45,-10],[58,0],[45,10],[28,15],[12,10],[0,0],[18,0],[28,-7],[38,0],[28,7],[18,0]],
    BOTTLE:[[0,0],[8,-8],[8,-25],[14,-31],[14,-42],[26,-42],[26,-31],[32,-25],[32,-8],[40,0],[40,28],[0,28],[0,0],[12,8],[28,8],[28,21],[12,21],[12,8]],
    WINDOW:[[0,0],[0,-36],[48,-36],[48,0],[0,0],[24,0],[24,-36],[24,-18],[0,-18],[48,-18]],
    LAMP:[[0,0],[12,-10],[24,-28],[36,-10],[48,0],[0,0],[24,0],[24,24],[10,30],[38,30],[24,24]],
    MASK:[[0,0],[10,-17],[25,-24],[41,-20],[52,-7],[54,10],[46,23],[31,29],[15,25],[3,14],[0,0],[14,2],[19,-3],[24,2],[31,2],[36,-3],[41,2],[34,14],[27,18],[20,14]]
  };
  const local=shapes[motif];
  if(!local)return null;
  const localLength=local.slice(1).reduce((sum,point,index)=>sum+Math.hypot(point[0]-local[index][0],point[1]-local[index][1]),0)||1;
  const physicalScale=Math.min(size,(distance*.94)/localLength);
  return local.map(point=>rotatePoint(point,heading,physicalScale,start));
}

function familyFor(style) {
  return ({curl: "cubic_bezier", segmented: "segmented_lines", branch: "branching", cross: "self_intersection", echo: "repeated_motif", cluster: "dense_cluster", knot: "knotted_orbit", fracture: "fractured_zigzag", orbit: "orbital_loop", web: "woven_web", coil: "coiled_form", petal: "petal_oscillation", lattice: "angular_lattice", hook: "hooked_turn", starburst: "radial_burst"})[style] || style;
}

function brushProfile(tool, pressure) {
  const base = .8 + pressure * 6.4;
  const profiles = {
    ink_line: [1, .92], soft_paint: [2.15, .72], dry_brush: [1.45, .76], fine_pen: [.42, .98],
    charcoal_grain: [1.35, .78], wash: [3.1, .62], stipple: [.78, .92], splatter: [.7, .88], subtractive: [1.7, 1],
  };
  const [width, opacity] = profiles[tool] || profiles.ink_line;
  return {baseWidth: round(base, 2), width: round(base * width, 2), opacity: round(opacity * (.9 + pressure * .1), 3)};
}

export class CanvasMechanics {
  constructor(seed, events, memory = new CanvasMemory()) {
    this.seed = Number(seed) >>> 0;
    this.events = events;
    this.memory = memory;
    this.position = [735, 48];
    this.brushDown = false;
    this.clock = 100;
    this.physicalActionCount = 0;
  }

  execute(action, decisionIndex) {
    const start = [...this.position];
    const count = clamp(Math.round(12 + action.movementDistance / 3.7 + (action.branchingDepth || 0) * 2), 12, 44);
    let points = [start];
    const figure=action.brushDown&&FIGURE_MOTIFS.has(action.motifHint)?figurativePrimitive(action.motifHint,start,action.targetDirection,action.movementDistance):null;
    if(figure){points=figure;}
    else{
      const step = action.movementDistance / (count - 1);
      let heading = action.targetDirection;
      for (let i = 1; i < count; i += 1) {
        const t = i / (count - 1);
        heading += action.curvature / (count - 1) + (styleOffset(action.movementStyle, t, i) + motifOffset(action.motifHint, t, i) * 3.2) / (count - 1);
        let x = points[i - 1][0] + Math.cos(heading) * step;
        let y = points[i - 1][1] + Math.sin(heading) * step;
        if (x < MARGIN || x > CANVAS_WIDTH - MARGIN) heading = Math.PI - heading;
        if (y < MARGIN || y > CANVAS_HEIGHT - MARGIN) heading = -heading;
        x = clamp(points[i - 1][0] + Math.cos(heading) * step, MARGIN, CANVAS_WIDTH - MARGIN);
        y = clamp(points[i - 1][1] + Math.sin(heading) * step, MARGIN, CANVAS_HEIGHT - MARGIN);
        points.push([round(x), round(y)]);
      }
    }
    const duration = Math.round(clamp(action.duration + action.hesitation, 90, 1500));
    const family = familyFor(action.movementStyle);
    if (!action.brushDown) {
      this.events.push({type: "move", action: "move_tip", timestamp: this.clock, duration, from: start, to: points.at(-1), decision: decisionIndex});
      this.clock += duration;
      this.position = [...points.at(-1)];
      this.memory.consecutiveLowChange += 1;
      this.physicalActionCount += 1;
      return {meaningful: false, change: 0, family, points};
    }
    this.events.push({type: "tip_down", timestamp: this.clock, point: start, decision: decisionIndex});
    this.brushDown = true;
    const profile = brushProfile(action.brushTool, action.pressure);
    this.events.push({type: "stroke", action: action.eraseIntent ? "erase_path" : "draw_path", timestamp: this.clock,
      duration, points, speed: action.speed, pressure: action.pressure,
      baseWidth: profile.baseWidth, width: profile.width, opacity: profile.opacity,
      color: action.color || "#111111", erase: action.eraseIntent, family, decision: decisionIndex,
      phase: action.phase, layerRole: action.layerRole, motifTransform: action.motifTransform,
      branchingDepth: action.branchingDepth, strokeCharacter: action.strokeCharacter, scale: action.scale,
      brushTool: action.brushTool, technique: action.technique, motifHint: action.motifHint || "NONE"});
    this.clock += duration;
    this.position = [...points.at(-1)];
    const change = this.memory.remember(points, family, action.eraseIntent);
    this.events.push({type: "tip_up", timestamp: this.clock, point: this.position, decision: decisionIndex});
    this.brushDown = false;
    if (action.hesitation > 0) this.events.push({type: "pause", timestamp: this.clock, duration: action.hesitation, point: this.position});
    this.clock += action.hesitation;
    this.physicalActionCount += 1;
    return {...change, family, points};
  }

  lift() {
    if (this.brushDown) this.events.push({type: "tip_up", timestamp: this.clock, point: this.position});
    this.brushDown = false;
  }
}
