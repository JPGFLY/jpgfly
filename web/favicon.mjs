import {renderFlyPortrait} from './art-engine.mjs?v=transparent-wings-3';

function installFlyFavicon(){
  const canvas=document.createElement('canvas');
  canvas.width=512;
  canvas.height=512;
  const ctx=canvas.getContext('2d',{alpha:false});
  renderFlyPortrait(ctx,{
    time:0,
    inkColor:'#b85f43',
    brushDown:false,
    background:'#ffffff'
  });
  const href=canvas.toDataURL('image/png');

  let links=[...document.querySelectorAll('link[rel~="icon"]')];
  if(!links.length){
    const link=document.createElement('link');
    link.rel='icon';
    link.type='image/png';
    document.head.appendChild(link);
    links=[link];
  }
  for(const link of links){
    link.type='image/png';
    link.sizes='512x512';
    link.href=href;
  }
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',installFlyFavicon,{once:true});
}else{
  installFlyFavicon();
}
