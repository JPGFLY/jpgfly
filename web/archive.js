import{artworkCard}from'./backroom.js?v=room-agents-1';

const grid=document.querySelector('#archive-grid');
const count=document.querySelector('#archive-count');
const more=document.querySelector('#load-more');
const form=document.querySelector('#archive-search-form');
const search=document.querySelector('#archive-search');
const clear=document.querySelector('#archive-search-clear');
const agentButtons=[...document.querySelectorAll('[data-archive-agent]')];

let offset=0;
const initial=new URLSearchParams(location.search);
let query=initial.get('q')?.trim()||'';
let agent=initial.get('agent')?.trim().toLowerCase()||'all';
if(!['all','jpgfly','sprayfly','dreamfly'].includes(agent))agent='all';
let timer=0;
if(search)search.value=query;
const pageSize=24;

function syncAgents(){for(const button of agentButtons)button.setAttribute('aria-pressed',String(button.dataset.archiveAgent===agent));}
function searchLabel(total){
  const who=agent==='all'?'':` · ${agent.toUpperCase()}`;
  if(!query)return `${total} ARCHIVED ROOM${total===1?'':'S'}${who}`;
  return `${total} RESULT${total===1?'':'S'} FOR "${query.toUpperCase()}"${who}`;
}

async function load(reset=false){
  if(reset){offset=0;grid.textContent='';}
  more.disabled=true;
  try{
    const params=new URLSearchParams({offset:String(offset),limit:String(pageSize)});
    if(query)params.set('q',query);
    if(agent!=='all')params.set('agent',agent);
    const response=await fetch(`/api/artworks?${params.toString()}`,{cache:'no-store'});
    if(!response.ok)throw new Error('archive unavailable');
    const data=await response.json();
    if(reset||offset===0)grid.textContent='';
    for(const item of data.artworks||[])grid.append(artworkCard(item));
    offset+=data.artworks.length;
    count.textContent=searchLabel(data.total);
    more.hidden=!data.hasMore;more.style.display=data.hasMore?'':'none';
    if(!data.total){const empty=document.createElement('div');empty.className='backroom-empty';empty.textContent=query?`No selected room contains "${query}".`:'No completed rooms exist in this room line yet.';grid.append(empty);}
  }catch(error){grid.textContent='';const empty=document.createElement('div');empty.className='backroom-empty';empty.textContent='The Backrooms archive could not be read.';grid.append(empty);}
  finally{more.disabled=false;}
}

function syncURL(){const url=new URL(location.href);if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');if(agent==='all')url.searchParams.delete('agent');else url.searchParams.set('agent',agent);history.replaceState(null,'',url);}
function applySearch(){query=(search.value||'').trim();syncURL();load(true);}
search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(applySearch,260);});
form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);applySearch();});
clear.addEventListener('click',()=>{clearTimeout(timer);search.value='';query='';search.focus();syncURL();load(true);});
for(const button of agentButtons)button.addEventListener('click',()=>{agent=button.dataset.archiveAgent||'all';syncAgents();syncURL();load(true);});
more.addEventListener('click',()=>load());
syncAgents();load(true);
