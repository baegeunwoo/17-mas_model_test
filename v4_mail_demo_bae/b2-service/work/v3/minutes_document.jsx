// The '원본' tab for text records: the original lines laid out on the team's A4 minutes form.
// Sections 3–5 come from the AI summary and change records, and say so on the sheet.
import React,{useState} from 'react';
import {Printer,FileText,AlignLeft,Download} from 'lucide-react';
import {Button} from './app';
import {minutesLayout} from './source_document.js';

const day=s=>s?s.replaceAll('-','.'):'';

function Block({b,focus}){
 const cls=id=>focus.includes(id)?'highlight':'';
 if(b.type==='heading')return <h4 id={'source-'+b.id} className={'ms-subhead '+cls(b.id)}>{b.number&&<span>{b.number}.</span>}{b.text}</h4>;
 if(b.type==='item')return <p id={'source-'+b.id} className={'ms-item depth-'+b.depth+' '+cls(b.id)}>{b.text}</p>;
 if(b.type==='table'){
  const width=Math.max(...b.rows.map(r=>r.cells.length));
  const rows=b.head?b.rows.slice(1):b.rows;
  return <table className="ms-body-table">{b.head&&<thead><tr id={'source-'+b.rows[0].id}>{b.rows[0].cells.map((c,i)=><th key={i}>{c}</th>)}</tr></thead>}
   <tbody>{rows.map(r=><tr key={r.id} id={'source-'+r.id} className={cls(r.id)}>{Array.from({length:width},(_,i)=><td key={i}>{r.cells[i]||''}</td>)}</tr>)}</tbody></table>;
 }
 return <p id={'source-'+b.id} className={'ms-text '+cls(b.id)}>{b.text}</p>;
}

// Summary items are shown as their original lines; a table row reads as '항목 · 내용 · 담당'.
function originalLines(points,lines){
 const text=Object.fromEntries((lines||[]).map(l=>[l.id,l.text]));const seen=new Set(),out=[];
 for(const p of points){
  const ids=(p.evidence||[]).filter(id=>id in text&&!seen.has(id));
  if(!ids.length){if(!(p.evidence||[]).length)out.push({key:p.id,text:p.text,due:p.due});continue}
  ids.forEach((id,i)=>{seen.add(id);out.push({key:p.id+id,id,text:text[id].split('|').map(s=>s.trim()).filter(s=>s&&s!=='-').join(' · ').replace(/^\s*[-·•*]\s*/,''),due:i===0?p.due:''})});
 }
 return out;
}

function Section({n,title,note,children,empty}){
 return <section className="ms-section"><h3><span>{n}</span>{title}{note&&<small>{note}</small>}</h3>{children||<p className="ms-empty">{empty||'해당 없음'}</p>}</section>;
}

export function MinutesDocument({meeting,projectName,authorName,points=[],changes=[],focus=[]}){
 const[plain,setPlain]=useState(false);
 const {header,blocks,agenda}=minutesLayout(meeting.lines);
 const agendaItems=agenda.length?agenda:(meeting.agendas||[]).filter(g=>g.topic_id).map(g=>g.title);
 const decisions=originalLines(points.filter(p=>p.kind==='결정사항'),meeting.lines);
 const followups=originalLines(points.filter(p=>p.kind==='후속 확인'),meeting.lines);
 const open=changes.filter(e=>['요청','보류'].includes(e.business_state));
 const v=(key,fallback)=>header[key]?.value||fallback||'—';
 return <div className="minutes-view">
  <div className="minutes-tools">
   <div className="segmented" role="group" aria-label="원본 보기 방식">
    <button className={!plain?'active':''} aria-pressed={!plain} onClick={()=>setPlain(false)}><FileText size={15}/>회의록 양식</button>
    <button className={plain?'active':''} aria-pressed={plain} onClick={()=>setPlain(true)}><AlignLeft size={15}/>원문 텍스트</button>
   </div>
   <div className="actions">{!plain&&<Button icon={Printer} onClick={()=>window.print()}>PDF로 저장·인쇄</Button>}<a className="button" href={'/api/v3/meetings/'+meeting.id+'/download'}><Download size={16}/>원본 파일</a></div>
  </div>
  {plain?<article className="paper source-lines">{meeting.revision>1&&<p className="muted">웹에서 수정한 본문입니다. 업로드한 원본 파일은 별도로 보관됩니다.</p>}{(meeting.lines||[]).map(l=><p id={'source-'+l.id} className={focus.includes(l.id)?'highlight':''} key={l.id}>{l.text}</p>)}</article>
  :<article className="minutes-sheet" aria-label="회의록 문서">
   <header className="ms-titlebar"><span>회 의 록</span><small>MEETING MINUTES</small></header>
   <table className="ms-info"><tbody>
    <tr><th>회의명</th><td colSpan={3}>{v('title',meeting.title)}</td></tr>
    <tr><th>프로젝트명</th><td colSpan={3}>{v('project',projectName)}</td></tr>
    <tr><th>일시</th><td>{v('date',day(meeting.date))}</td><th>장소</th><td>{v('place')}</td></tr>
    <tr><th>참석자</th><td colSpan={3}>{v('attendees')}</td></tr>
    <tr><th>작성자</th><td>{v('writer',authorName)}</td><th>작성일</th><td>{day((meeting.created_at||'').slice(0,10))||'—'}</td></tr>
   </tbody></table>
   <Section n="1" title="회의 안건" note={agenda.length?'':agendaItems.length?'주제별 안건 기준':''}>{agendaItems.length>0&&<ol className="ms-agenda">{agendaItems.map((a,i)=><li key={i}>{a}</li>)}</ol>}</Section>
   <Section n="2" title="논의 내용" note="회의록 원문">{blocks.length>0&&<div className="ms-body">{blocks.map((b,i)=><Block key={b.id||i} b={b} focus={focus}/>)}</div>}</Section>
   <Section n="3" title="결정 사항" note="AI 정리 기준">{decisions.length>0&&<ul className="ms-list">{decisions.map(p=><li key={p.key}>{p.text}</li>)}</ul>}</Section>
   <Section n="4" title="추가 확인 사항" note="요청·보류 중인 변경 기록">{open.length>0&&<ul className="ms-list">{open.map(e=><li key={e.id}><b>{e.title}</b> — {e.after} <em>({e.business_state})</em></li>)}</ul>}</Section>
   <Section n="5" title="후속 조치" note="AI 정리 기준">{followups.length>0&&<table className="ms-body-table ms-actions"><thead><tr><th>내용</th><th>기한</th></tr></thead><tbody>{followups.map(p=><tr key={p.key}><td>{p.text}</td><td>{day(p.due)||'—'}</td></tr>)}</tbody></table>}</Section>
   <footer className="ms-footer"><span>PNT 회의록</span><span>{meeting.revision>1?`수정본 ${meeting.revision}`:'최초 등록본'}</span></footer>
  </article>}
 </div>;
}
