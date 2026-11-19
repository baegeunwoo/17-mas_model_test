import React from 'react';
import {ArrowUpRight} from 'lucide-react';
import {Button,Empty} from './app';
import {agendaView} from './agenda_topics.js';

const day=s=>s?s.replaceAll('-','.'):'날짜 미정';

export function AgendaPanel({meeting,meetings,busy,onSource,onOpenMeeting,onRetry}){
 const v=agendaView(meeting,meetings);
 if(!v.groups.length)return <>
  {v.error&&<p className="agenda-note warning" role="alert">주제 묶기를 하지 못했습니다. {v.error}</p>}
  <Empty>{busy?'분석이 끝나면 주제별 안건이 표시됩니다.':'아직 주제별로 묶은 결과가 없습니다.'}{!busy&&onRetry&&<Button onClick={onRetry}>다시 분석</Button>}</Empty>
 </>;
 return <article className="agenda-view">
  <p className="muted">AI가 회의록 문장을 주제별로 묶었습니다. 문장은 원문 그대로이며, 같은 프로젝트의 다른 회의에서 나온 같은 주제도 함께 표시합니다.
   {' '}주제 {v.topics}개{v.carried?` · 이전 회의에서 이어진 주제 ${v.carried}개`:''}</p>
  {v.stale&&<p className="agenda-note warning">본문을 수정하기 전 내용으로 묶은 결과입니다. 다시 분석하면 새 본문 기준으로 바뀝니다.</p>}
  {v.error&&<p className="agenda-note warning" role="alert">이번 분석에서 주제 묶기를 하지 못했습니다. {v.error}</p>}
  {v.groups.map(g=><section className={'agenda-group'+(g.misc?' misc':'')} key={g.key}>
   <div className="agenda-head">
    <h2>{g.title}</h2><span className="muted">{g.lines.length}행</span>
    {g.carried&&<span className="status">이전 회의에서 이어짐</span>}
    {!g.carried&&g.continues&&<span className="status">이후 회의로 이어짐</span>}
   </div>
   <ul className="agenda-lines">{g.lines.map(l=><li key={l.id}>{l.text}</li>)}</ul>
   <div className="agenda-tools">
    {g.appearances.length>1&&<div className="agenda-trail" aria-label={g.title+' 주제가 나온 회의'}><span className="muted">이 주제가 나온 회의</span>
     {g.appearances.map(a=>a.current?<span className="agenda-chip current" key={a.id}>{day(a.date)} · 이 회의</span>
      :<button className="agenda-chip" key={a.id} title={a.title} onClick={()=>onOpenMeeting(a.id)}>{day(a.date)} · {a.title}</button>)}
    </div>}
    <button className="agenda-source" onClick={()=>onSource(g.lines.map(l=>l.id))}>원문에서 보기 <ArrowUpRight size={14}/></button>
   </div>
  </section>)}
 </article>;
}
