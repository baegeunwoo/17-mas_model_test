import React,{useState,useEffect} from 'react';
import {ArrowUpRight,ChevronDown,ChevronUp} from 'lucide-react';
import {api,Button,Empty} from './app';
import {agendaView} from './agenda_topics.js';

const day=s=>s?s.replaceAll('-','.'):'날짜 미정';
const short=s=>s?s.slice(5).replace('-','.'):'미정';
// Display only: a leading list marker ('- ', '· ', '1) ') is dropped; the words are untouched.
const clean=t=>t.replace(/^\s*(?:[-·•*▪◦○∙]|\d{1,2}[.)])\s+/,'');
const PREVIEW=3;
const STATUS={'최초':['first','이 회의에서 처음 나온 주제입니다'],'진행중':['ongoing','이전 회의부터 이어지고, 요청·보류 중인 기록이 남아 있습니다'],'완료':['done','이 주제의 변경 기록이 모두 합의·철회로 정리됐습니다']};
// Per meeting: 완료 when the project-wide record is settled, else 최초 at its first meeting, else 진행중.
const statusOf=(g,flow)=>flow?.status==='완료'?'완료':g.carried?'진행중':'최초';
export function StatusBadge({status,detail}){const[c,t]=STATUS[status]||[];return c?<span className={'agenda-flag '+c} title={t+(detail?' · '+detail:'')}>{status}</span>:null}

export function AgendaPanel({meeting,meetings,busy,onSource,onOpenMeeting,onRetry}){
 const v=agendaView(meeting,meetings);
 const[open,setOpen]=useState({}),[flow,setFlow]=useState({});
 useEffect(()=>{let live=true;api('/v3/projects/'+meeting.project_id+'/topics').then(d=>{if(live)setFlow(Object.fromEntries(d.topics.map(t=>[t.id,t])))}).catch(()=>{});return()=>{live=false}},[meeting.project_id,meeting.id,meeting.version]);
 if(!v.groups.length)return <>
  {v.error&&<p className="agenda-note warning" role="alert">주제 묶기를 하지 못했습니다. {v.error}</p>}
  <Empty>{busy?'분석이 끝나면 주제별 안건이 표시됩니다.':'아직 주제별로 묶은 결과가 없습니다.'}{!busy&&onRetry&&<Button onClick={onRetry}>다시 분석</Button>}</Empty>
 </>;
 const long=v.groups.filter(g=>g.lines.length>PREVIEW);
 const all=long.length>0&&long.every(g=>open[g.key]);
 const jump=key=>document.getElementById('agenda-'+key)?.scrollIntoView({block:'start',behavior:'smooth'});
 const counts={};v.groups.filter(g=>!g.misc).forEach(g=>{const st=statusOf(g,flow[g.key]);counts[st]=(counts[st]||0)+1});
 return <article className="agenda-view">
  <div className="agenda-bar">
   <p className="muted">주제 <b>{v.topics}</b>개 {['최초','진행중','완료'].filter(s=>counts[s]).map(s=><span key={s} className={'agenda-flag '+STATUS[s][0]}>{s} {counts[s]}</span>)} · 문장은 회의록 원문 그대로입니다.</p>
   {long.length>0&&<button className="link-button" onClick={()=>setOpen(all?{}:Object.fromEntries(long.map(g=>[g.key,true])))}>{all?'모두 접기':'모두 펼치기'}</button>}
  </div>
  {v.stale&&<p className="agenda-note warning">본문을 수정하기 전 내용으로 묶은 결과입니다. 다시 분석하면 새 본문 기준으로 바뀝니다.</p>}
  {v.error&&<p className="agenda-note warning" role="alert">이번 분석에서 주제 묶기를 하지 못했습니다. {v.error}</p>}
  {v.groups.length>4&&<nav className="agenda-index" aria-label="주제 바로가기">{v.groups.map(g=><button key={g.key} className={g.misc?'misc':''} onClick={()=>jump(g.key)}>{g.title}<small>{g.lines.length}</small></button>)}</nav>}
  <div className="agenda-table">
   {v.groups.map(g=>{
    const expanded=open[g.key]||g.lines.length<=PREVIEW,shown=expanded?g.lines:g.lines.slice(0,PREVIEW);
    return <section id={'agenda-'+g.key} className={'agenda-row'+(g.misc?' misc':'')} key={g.key} aria-label={g.title}>
     <div className="agenda-topic">
      <h2>{g.title}</h2>
      <span className="muted">{g.lines.length}문장</span>
      {!g.misc&&<StatusBadge status={statusOf(g,flow[g.key])} detail={g.appearances.length>1?g.appearances.length+'개 회의에서 다룸':''}/>}
     </div>
     <div className="agenda-content">
      <ul className="agenda-sentences">{shown.map(l=><li key={l.id} title={l.text}>{clean(l.text)}</li>)}</ul>
      {g.lines.length>PREVIEW&&<button className="agenda-more" aria-expanded={expanded} onClick={()=>setOpen(o=>({...o,[g.key]:!o[g.key]}))}>{expanded?<>접기 <ChevronUp size={14}/></>:<>{g.lines.length-PREVIEW}문장 더 보기 <ChevronDown size={14}/></>}</button>}
      {g.appearances.length>1&&<div className="agenda-trail" aria-label={g.title+' 주제가 나온 회의'}><span>나온 회의</span>
       {g.appearances.map(a=>a.current?<span className="agenda-chip current" key={a.id} title="이 회의">{short(a.date)} 이 회의</span>
        :<button className="agenda-chip" key={a.id} title={day(a.date)+' '+a.title} onClick={()=>onOpenMeeting(a.id)}>{short(a.date)}</button>)}
      </div>}
     </div>
     <button className="agenda-source" title="원본 탭에서 이 문장들 보기" onClick={()=>onSource(g.lines.map(l=>l.id))}>원문 <ArrowUpRight size={14}/></button>
    </section>})}
  </div>
 </article>;
}
