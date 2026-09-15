// Shared action contract only. Artistic decisions live in Python on the server.
export const MOVEMENT_STYLES=['sweep','segmented','loop','spiral','curl','jitter','branch','cluster','echo','cross','contour','accent','bold','knot','fracture','orbit','web','coil','petal','lattice','hook','starburst'];
export const ART_PALETTE=['#ff3b30','#ff9500','#ffd60a','#32d74b','#00d4ff','#0a84ff','#5e5ce6','#bf5af2','#ff2d8d','#111111'];
export const BRUSH_TOOLS=['ink_line','soft_paint','dry_brush','fine_pen','charcoal_grain','wash','stipple','splatter','subtractive'];
export const DRAWING_TECHNIQUES=['continuous','hatching','cross_hatching','stippling','layered_glazing','overpainting','smudged_dragging','motif_repetition_different_brush','selective_erasure'];
const HEX_COLOR=/^#[0-9a-fA-F]{6}$/;
const MOTIF_HINT=/^[A-Z0-9_]{1,32}$/;
export const REQUIRED_ACTION_FIELDS=['intent','targetDirection','movementDistance','curvature','speed','duration','brushDown','pressure','hesitation','exploration','attentionTarget','eraseIntent','movementStyle','relationshipToExistingMarks','motifReference','confidence','reason','phase','scale','layerRole','motifTransform','branchingDepth','strokeCharacter','brushTool','technique'];
export function validateBrainAction(action){
  if(!action||REQUIRED_ACTION_FIELDS.some(field=>!(field in action)))return false;
  if(!['MOVE','FINISH_ARTWORK'].includes(action.intent))return false;
  if('points' in action||'path' in action)return false;
  if(action.intent==='FINISH_ARTWORK')return action.brushDown===false&&action.movementDistance===0;
  return Number.isFinite(action.targetDirection)&&Number.isFinite(action.movementDistance)&&Number.isFinite(action.curvature)&&Number.isFinite(action.speed)&&Number.isFinite(action.pressure)&&typeof action.brushDown==='boolean'&&MOVEMENT_STYLES.includes(action.movementStyle)&&HEX_COLOR.test(action.color)&&(!('motifHint' in action)||MOTIF_HINT.test(action.motifHint))&&BRUSH_TOOLS.includes(action.brushTool)&&DRAWING_TECHNIQUES.includes(action.technique);
}
