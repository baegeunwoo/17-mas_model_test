// Lay out a text meeting record as the team's minutes form. Every body line keeps its id and
// original text; only the header fields (회의명·일시·장소·참석자·작성자) are lifted into the form table.
const FIELDS=[['title',/^(회의\s*명|회의\s*제목|제목)$/],['date',/^(일시|일자|날짜|회의\s*일시)$/],['place',/^(장소|회의\s*장소)$/],
 ['attendees',/^(참석자|참석|참석\s*인원)$/],['writer',/^(작성자|작성)$/],['project',/^(프로젝트|프로젝트\s*명)$/]];
const HEADER=/^\s*([^:|：]{1,12}?)\s*[:|：]\s*(.+)$/;
const HEADING=/^\s*(?:(\d{1,2})[.)]\s+(.+)|[■□◆◇▶▣]\s*(.+)|\[(.+)\]|#{1,3}\s+(.+))$/;
const BULLET=/^(\s*)[-·•*▪◦○∙]\s*(.+)$/;

function field(text){
 const m=text.match(HEADER);if(!m)return null;
 const key=FIELDS.find(([,re])=>re.test(m[1].trim()));
 return key?{key:key[0],value:m[2].trim()}:null;
}

export function minutesLayout(lines){
 const header={},blocks=[];let started=false,table=null;
 for(const line of lines||[]){
  const text=line.text||'';
  if(!text.trim())continue;
  const f=!started&&field(text);
  if(f&&!(f.key in header)){header[f.key]={value:f.value,id:line.id};continue}
  started=true;
  const cells=text.includes('|')?text.split('|').map(s=>s.trim()):null;
  if(cells&&cells.length>=2){
   if(!table){table={type:'table',rows:[]};blocks.push(table)}
   table.rows.push({id:line.id,cells});continue;
  }
  table=null;
  const h=text.match(HEADING);
  if(h){blocks.push({type:'heading',id:line.id,number:h[1]||'',text:(h[2]||h[3]||h[4]||h[5]).trim()});continue}
  const b=text.match(BULLET);
  if(b){blocks.push({type:'item',id:line.id,depth:b[1].replace(/\t/g,'  ').length>=2?1:0,text:b[2].trim()});continue}
  blocks.push({type:'text',id:line.id,text:text.trim()});
 }
 // A table's first row is a column header when no other row repeats its shape of short labels.
 for(const t of blocks.filter(b=>b.type==='table'))t.head=t.rows.length>1&&t.rows[0].cells.every(c=>c&&c.length<=8&&!/\d/.test(c));
 const agenda=blocks.filter(b=>b.type==='heading').map(b=>b.text);
 return {header,blocks,agenda};
}
