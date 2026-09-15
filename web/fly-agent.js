const style=document.createElement('style');
style.textContent=`
@keyframes jpgfly-white-hover{
  0%,100%{transform:translateY(-4px) rotate(-.5deg)}
  50%{transform:translateY(4px) rotate(.5deg)}
}
.fly,.jpgfly-page-fly,.fly-art{
  display:block!important;
  visibility:visible!important;
  opacity:1!important;
  object-fit:contain!important;
  filter:none!important;
  box-shadow:none!important;
  animation:jpgfly-white-hover 7.5s ease-in-out infinite!important;
  will-change:transform
}
.fly,.fly-art{background:#000!important}
.jpgfly-page-fly{
  background:transparent!important;
  mix-blend-mode:screen!important;
}
@media(prefers-reduced-motion:reduce){
  .fly,.jpgfly-page-fly,.fly-art{animation:none!important}
}
`;
document.head.append(style);

for(const fly of document.querySelectorAll('.fly,.jpgfly-page-fly,.fly-art')){
  fly.src='/images/fly.png?v=white-flat-3';
  fly.addEventListener('error',()=>{fly.style.display='none'},{once:true});
}
