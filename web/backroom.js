export const TIME_STANDARD='UTC';
export const formatDate=value=>{if(!value)return'-';const date=new Date(value);if(Number.isNaN(date.valueOf()))return'-';return new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false,timeZoneName:'short'}).format(date)};

export function artworkCard(item){
  const link=document.createElement('a');link.className='backroom-card';link.href=item.url;
  const image=document.createElement('img');image.src=item.preview;image.loading='lazy';image.alt=`${item.room_code||'JPGFLY room'} artwork`;
  const meta=document.createElement('div');meta.className='backroom-meta';

  const heading=document.createElement('strong'),code=document.createElement('span'),status=document.createElement('span');
  status.className='backroom-status';code.textContent=item.room_code||`ROOM-${String(item.room_number||0).padStart(4,'0')}`;status.textContent=item.quality_tier==='DUMB_DUMB'?'ARCHIVED · DUMB DUMB':'ARCHIVED';heading.append(code,status);

  const date=document.createElement('span');date.textContent=formatDate(item.completed_at);

  const title=document.createElement('span');title.className='backroom-concept';title.textContent=item.room_title||'Unnamed room';

  const description=document.createElement('span');description.className='backroom-description';
  description.textContent=item.room_description||item.concept||'A completed fly drawing.';

  const commentary=Array.isArray(item.public_commentary)?item.public_commentary:[];
  const latest=commentary.at(-1);
  const history=document.createElement('span');history.className='backroom-history-preview';
  history.textContent=latest?.text||((item.thought_fragments||[]).at(-1))||'No public history note was recorded for this room.';

  meta.append(heading,date,title,description,history);
  link.append(image,meta);
  return link;
}

export function renderArtworkGrid(root,items,emptyText){
  root.textContent='';
  if(!items.length){
    const empty=document.createElement('div');empty.className='backroom-empty';empty.textContent=emptyText;root.append(empty);return;
  }
  items.forEach(item=>root.append(artworkCard(item)));
}

export async function loadBackroom(){
  const recent=document.querySelector('[data-recent-artworks]');
  if(!recent)return;
  try{
    const response=await fetch('/api/artworks/recent?limit=9',{cache:'no-store'});
    if(!response.ok)throw new Error();
    const data=await response.json();
    renderArtworkGrid(recent,data.artworks||[],'The fly has not completed a room yet.');
  }catch(_){
    renderArtworkGrid(recent,[],'The archive is temporarily quiet.');
  }
}
if(document.querySelector('[data-recent-artworks]'))loadBackroom();
