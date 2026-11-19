// Subjects of one meeting as stored by the analysis (meeting.agendas), with the other
// meetings of the same project where each subject came up. Text is always the original line.
const when=m=>[m.date||'9999-99-99',m.created_at||''];
const byDate=(a,b)=>{const[x,y]=[when(a),when(b)];return x[0]<y[0]?-1:x[0]>y[0]?1:x[1]<y[1]?-1:x[1]>y[1]?1:0};

export function agendaView(meeting,meetings=[]){
 const text=Object.fromEntries((meeting.lines||[]).map(l=>[l.id,l.text]));
 const project=[...meetings.filter(m=>m.id!==meeting.id&&m.project_id===meeting.project_id&&!m.deleted_at),meeting].sort(byDate);
 const groups=(meeting.agendas||[]).map(g=>{
  const lines=(g.lines||[]).filter(id=>id in text).map(id=>({id,text:text[id].trim()}));
  const appearances=g.topic_id?project.filter(m=>m.id===meeting.id||(m.agendas||[]).some(a=>a.topic_id===g.topic_id)).map(m=>({id:m.id,title:m.title,date:m.date||'',current:m.id===meeting.id})):[];
  const position=appearances.findIndex(a=>a.current);
  return {key:g.topic_id||'misc',title:g.title,misc:!g.topic_id,lines,appearances,carried:position>0,continues:position>=0&&position<appearances.length-1};
 }).filter(g=>g.lines.length);
 // Unassigned rows ('기타') go last; subjects keep the order they first appear in the meeting.
 groups.sort((a,b)=>a.misc-b.misc);
 return {
  groups,
  topics:groups.filter(g=>!g.misc).length,
  carried:groups.filter(g=>g.carried).length,
  stale:meeting.agenda_revision!=null&&meeting.revision!=null&&meeting.agenda_revision!==meeting.revision,
  error:meeting.agenda_error||'',
 };
}
