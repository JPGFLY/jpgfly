import{artworkCard}from'./backroom.js?v=identity-utc-6';

const grid=document.querySelector('#archive-grid');
const count=document.querySelector('#archive-count');
const more=document.querySelector('#load-more');
const form=document.querySelector('#archive-search-form');
const search=document.querySelector('#archive-search');
const clear=document.querySelector('#archive-search-clear');

let offset=0;
let query=new URLSearchParams(location.search).get('q')?.trim()||'';
let timer=0;
if(search)search.value=query;
const pageSize=24;

function searchLabel(total){
  if(!query)return `${total} ARCHIVED ROOM${total===1?'':'S'}`;
  return `${total} RESULT${total===1?'':'S'} FOR "${query.toUpperCase()}"`;
}

async function load(reset=false){
  if(reset){
    offset=0;
    grid.textContent='';
  }

  more.disabled=true;

  try{
    const params=new URLSearchParams({
      offset:String(offset),
      limit:String(pageSize)
    });
    if(query)params.set('q',query);

    const response=await fetch(`/api/artworks?${params.toString()}`,{cache:'no-store'});
    if(!response.ok)throw new Error('archive unavailable');

    const data=await response.json();

    if(reset||offset===0)grid.textContent='';

    for(const item of data.artworks||[])grid.append(artworkCard(item));

    offset+=data.artworks.length;
    count.textContent=searchLabel(data.total);

    more.hidden=!data.hasMore;
    more.style.display=data.hasMore?'':'none';

    if(!data.total){
      const empty=document.createElement('div');
      empty.className='backroom-empty';
      empty.textContent=query
        ? `No Backrooms room contains "${query}".`
        : 'No completed rooms yet. Return to the live room and watch the fly make one.';
      grid.append(empty);
    }
  }catch(error){
    grid.textContent='';
    const empty=document.createElement('div');
    empty.className='backroom-empty';
    empty.textContent='The Backrooms archive could not be read.';
    grid.append(empty);
  }finally{
    more.disabled=false;
  }
}

function applySearch(){
  query=(search.value||'').trim();
  const url=new URL(location.href);
  if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');
  history.replaceState(null,'',url);
  load(true);
}

search.addEventListener('input',()=>{
  clearTimeout(timer);
  timer=setTimeout(applySearch,260);
});

form.addEventListener('submit',event=>{
  event.preventDefault();
  clearTimeout(timer);
  applySearch();
});

clear.addEventListener('click',()=>{
  clearTimeout(timer);
  search.value='';
  query='';
  search.focus();
  load(true);
});

more.addEventListener('click',()=>load());
load(true);
