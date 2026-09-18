import * as core from './art-engine-core.mjs?v=clean-fly-head-20260917-8';
export * from './art-engine-core.mjs?v=clean-fly-head-20260917-8';

function cleanFacePaths(ctx,draw){
  const path=[];

  const pointsForPath=()=>{
    const points=[];
    for(const command of path){
      if(command[0]==='M'||command[0]==='L')points.push([command[1],command[2]]);
      else if(command[0]==='Q'){
        points.push([command[1],command[2]],[command[3],command[4]]);
      }else if(command[0]==='B'){
        points.push([command[1],command[2]],[command[3],command[4]],[command[5],command[6]]);
      }else if(command[0]==='A'){
        const [,x,y,r]=command;
        points.push([x-r,y-r],[x+r,y+r]);
      }
    }
    return points;
  };

  const isFaceArtifact=()=>{
    if(!path.length||path.length>4)return false;
    const points=pointsForPath();
    if(!points.length)return false;

    // Anything this small and fully confined to the old face-detail zone is
    // decorative facial geometry, not a wing, body segment, leg or brush.
    // This removes the mouth, antennae, bristles and every fin-like leftover
    // from both the homepage portrait and the live canvas Fly.
    return points.every(([x,y])=>
      Number.isFinite(x)&&Number.isFinite(y)
      &&x>=28&&x<=60
      &&y>=-30&&y<=18
    );
  };

  const proxy=new Proxy(ctx,{
    get(target,prop){
      if(prop==='beginPath')return(...args)=>{
        path.length=0;
        return target.beginPath(...args);
      };
      if(prop==='moveTo')return(x,y,...rest)=>{
        path.push(['M',Number(x),Number(y)]);
        return target.moveTo(x,y,...rest);
      };
      if(prop==='lineTo')return(x,y,...rest)=>{
        path.push(['L',Number(x),Number(y)]);
        return target.lineTo(x,y,...rest);
      };
      if(prop==='quadraticCurveTo')return(cpx,cpy,x,y,...rest)=>{
        path.push(['Q',Number(cpx),Number(cpy),Number(x),Number(y)]);
        return target.quadraticCurveTo(cpx,cpy,x,y,...rest);
      };
      if(prop==='bezierCurveTo')return(cp1x,cp1y,cp2x,cp2y,x,y,...rest)=>{
        path.push(['B',Number(cp1x),Number(cp1y),Number(cp2x),Number(cp2y),Number(x),Number(y)]);
        return target.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,x,y,...rest);
      };
      if(prop==='arc')return(x,y,r,start,end,...rest)=>{
        path.push(['A',Number(x),Number(y),Number(r),Number(start),Number(end)]);
        return target.arc(x,y,r,start,end,...rest);
      };
      if(prop==='stroke')return(...args)=>{
        if(args.length===0&&isFaceArtifact())return undefined;
        return target.stroke(...args);
      };
      const value=Reflect.get(target,prop,target);
      return typeof value==='function'?value.bind(target):value;
    },
    set(target,prop,value){
      Reflect.set(target,prop,value,target);
      return true;
    }
  });
  return draw(proxy);
}

export function renderFlyOverlay(ctx,tip,brushDown=false,time=0,inkColor='#4aa3a1'){
  return cleanFacePaths(ctx,cleanCtx=>core.renderFlyOverlay(cleanCtx,tip,brushDown,time,inkColor));
}

export function renderFlyPortrait(ctx,options={}){
  return cleanFacePaths(ctx,cleanCtx=>core.renderFlyPortrait(cleanCtx,options));
}
