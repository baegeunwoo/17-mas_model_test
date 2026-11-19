// Project subject flow: one row per subject linked across meetings, expandable into the
// meeting-by-meeting trail of original lines and change records. No approval state here.
import React,{useState,useEffect} from 'react';
import {ArrowRight,ArrowUpRight,ChevronDown,ChevronRight,FolderOpen,Pencil} from 'lucide-react';
import {api,Empty,Button,Modal} from './app';
import {displayChange} from './change_display';
import {StatusBadge} from './agenda_view';

const day=s=>s?s.replaceAll('-','.'):'날짜 미정';
const short=s=>s?s.slice(5).replace('-','.'):'미정';
const stateLabel=s=>s==='확정'?'합의':s;
const stateClass=s=>'status '+(['요청','보류'].includes(s)?'warning':s==='철회'?'muted-status':'');
const FILTERS=[['all','전체 주제',d=>d.topics.length,()=>true],['multi','여러 회의에 걸친 주제',d=>d.multi,t=>t.meeting_count>1],['open','미결이 남은 주제',d=>d.open_topics,t=>t.open.length>0]];

function Value({change}){
 if(!change)return <span className="muted">변경 기록 없음</span>;
 const v=displayChange(change);
 return <span className="topic-value"><span className={stateClass(change.business_state)}>{stateLabel(change.business_state)}</span>
  {v.transition?<><span className="before">{v.before}</span><ArrowRight size={13}/><b>{v.after}{v.unit&&' '+v.unit}</b></>:<b>{v.after}</b>}</span>;
}

function MeetingLink({date,title,onClick}){
 return <button className="topic-meeting" title={title} onClick={e=>{e.stopPropagation();onClick()}}><time>{day(date)}</time><span>{title}</span></button>;
}

function RenameDialog({project,close,onSaved}){
 const[name,setName]=useState(project.name),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function save(){setBusy(true);setError('');try{onSaved(await api('/v3/projects/'+project.id,'PATCH',{name}))}catch(e){setError(e.message);setBusy(false)}}
 return <Modal title="프로젝트 이름 변경" close={()=>{if(!busy)close()}} footer={<><Button onClick={close} disabled={busy}>취소</Button><Button primary disabled={busy||name.trim().length<2||name.trim()===project.name} onClick={save}>{busy?'저장 중…':'저장'}</Button></>}>
  <label>프로젝트 이름<input autoFocus maxLength={120} value={name} placeholder="예: 동진 제박기 3호기" onChange={e=>setName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&name.trim().length>=2)save()}}/></label>
  <p className="muted">코드 {project.id}는 바뀌지 않습니다. 회의록·변경이력은 그대로 연결됩니다.</p>
  {error&&<p role="alert" className="error-box">{error}</p>}
 </Modal>;
}

export function TopicFlowPanel({projects,projectId,meetingCount,person,canRename,signature,onProject,onRenamed,onOpenMeeting,onOpenHistory}){
 const[data,setData]=useState(null),[error,setError]=useState(''),[open,setOpen]=useState({}),[filter,setFilter]=useState('all'),[renaming,setRenaming]=useState(false);
 useEffect(()=>{setOpen({});setData(null);setFilter('all')},[projectId]);
 useEffect(()=>{if(!projectId)return;let live=true;setError('');
  api('/v3/projects/'+projectId+'/topics').then(d=>{if(live)setData(d)}).catch(e=>{if(live)setError(e.message)});
  return()=>{live=false}},[projectId,signature]);
 const project=projects.find(p=>p.id===projectId);
 const toggle=id=>setOpen(o=>({...o,[id]:!o[id]}));
 const shown=data?data.topics.filter(FILTERS.find(f=>f[0]===filter)[3]):[];
 const all=shown.length>0&&shown.every(t=>open[t.id]);
 let body;
 if(error)body=<p className="error-box" role="alert">{error}</p>;
 else if(!data)body=<p className="muted">불러오는 중…</p>;
 else if(!data.topics.length)body=<Empty>{data.meetings?'아직 주제별로 묶은 회의록이 없습니다. 회의록을 분석하면 주제가 표시됩니다.':'이 프로젝트에 등록된 회의록이 없습니다.'}</Empty>;
 else body=<>
  <div className="tf-toolbar">
   <div className="tf-filters" role="group" aria-label="주제 보기">
    {FILTERS.map(([key,label,count])=><button key={key} className={filter===key?'active':''} aria-pressed={filter===key} onClick={()=>setFilter(key)}><b>{count(data)}</b><span>{label}</span></button>)}
   </div>
   <button className="link-button" disabled={!shown.length} onClick={()=>setOpen(all?{}:Object.fromEntries(shown.map(t=>[t.id,true])))}>{all?'모두 접기':'모두 펼치기'}</button>
  </div>
  {data.pending>0&&<p className="agenda-note">아직 주제를 묶지 않은 회의록 {data.pending}건은 이 표에 빠져 있습니다.</p>}
  <div className="tf-table" role="table" aria-label={(project?.name||'')+' 주제별 안건 흐름'}>
   <div className="tf-row head" role="row"><span role="columnheader" className="tf-rev-head">리비전 노트</span><span role="columnheader">주제</span><span role="columnheader">지금 값 (가장 최근 기록)</span><span role="columnheader">미결</span></div>
   {shown.map(t=>{const last=t.open[t.open.length-1];return <div className={'tf-item'+(open[t.id]?' open':'')} key={t.id}>
    <div className="tf-row" role="row" onClick={()=>toggle(t.id)}>
     <button className={'tf-expand'+(open[t.id]?' open':'')} aria-expanded={!!open[t.id]} title={open[t.id]?'리비전 노트 접기':'회의별 리비전 노트 보기'} aria-label={t.title+' 리비전 노트 '+t.meeting_count+'건 '+(open[t.id]?'접기':'보기')} onClick={e=>{e.stopPropagation();toggle(t.id)}}>{open[t.id]?<ChevronDown size={14}/>:<ChevronRight size={16}/>}</button>
     <span role="cell" className="tf-topic"><b>{t.title}<StatusBadge status={t.status}/></b>
      <span className="tf-trail" aria-label={'나온 회의 '+t.meeting_count+'건'}>{t.steps.map((s,i)=><i key={s.meeting_id} title={day(s.date)+' '+s.title} className={i===t.steps.length-1?'latest':''}/>)}<small>{t.meeting_count>1?`${short(t.first.date)} → ${short(t.last.date)}`:short(t.first.date)}</small></span></span>
     <span role="cell"><Value change={t.current}/>{t.current&&<button className="tf-source" title="이 회의록의 원본 열기" onClick={e=>{e.stopPropagation();onOpenMeeting(t.current.meeting_id,t.current.evidence||[])}}>{day(t.current.date)} · <span>{t.current.meeting_title}</span></button>}</span>
     <span role="cell">{last?<span className="tf-open"><span>{last.title}: {last.after}</span>{t.open.length>1&&<small>외 {t.open.length-1}건</small>}</span>:<span className="muted">없음</span>}</span>
    </div>
    {open[t.id]&&<div className="tf-detail">
     {t.open.length>0&&<div className="topic-open"><h4>미결 사항 {t.open.length}건</h4><ul>{t.open.map((o,i)=><li key={i}><span className={stateClass(o.business_state)}>{stateLabel(o.business_state)}</span><b>{o.title}</b><span>{o.after}</span><small className="muted">{day(o.date)}</small></li>)}</ul></div>}
     <ol className="topic-steps">{t.steps.map((s,i)=><li key={s.meeting_id}>
      <span className={'timeline-dot '+(i===t.steps.length-1?'latest':'')}/>
      <div className="topic-step-head"><MeetingLink date={s.date} title={s.title} onClick={()=>onOpenMeeting(s.meeting_id,s.lines.map(l=>l.id))}/>{i===0&&<span className="status">최초</span>}{i>0&&i===t.steps.length-1&&<span className="status">최근</span>}{s.stale&&<span className="status warning">본문 수정 전 기준</span>}</div>
      <ul className="agenda-lines">{s.lines.map(l=><li key={l.id} title={l.text}>{l.text.replace(/^\s*(?:[-·•*▪◦○∙]|\d{1,2}[.)])\s+/,'')}</li>)}</ul>
      {s.changes.length>0&&<ul className="topic-changes">{s.changes.map(c=><li key={c.id}><small className="muted">{c.category} · {c.title}</small><Value change={c}/></li>)}</ul>}
     </li>)}</ol>
     <div className="tf-actions">
      {t.change_count>0&&onOpenHistory&&<button className="agenda-source" onClick={onOpenHistory}>변경이력에서 보기 <ArrowUpRight size={14}/></button>}
      <button className="agenda-source" onClick={()=>onOpenMeeting(t.last.meeting_id,t.steps[t.steps.length-1].lines.map(l=>l.id))}>최근 회의록 원본 열기 <ArrowUpRight size={14}/></button>
     </div>
    </div>}
   </div>})}
   {!shown.length&&<Empty>이 조건에 맞는 주제가 없습니다.</Empty>}
  </div>
 </>;
 return <section className="topic-flow">
  <div className="tf-head">
   <span className="eyebrow">주제별 안건 흐름</span>
   <div className="tf-title"><h1><span className="tf-label">프로젝트</span>{project?.name||'프로젝트 없음'}{data?.subject&&!project?.name.includes(data.subject)&&<span className="tf-subject" title="회의록 제목에 공통으로 나온 말입니다">{data.subject}</span>}</h1>
    {project&&canRename(project)&&<Button icon={Pencil} onClick={()=>setRenaming(true)}>이름 변경</Button>}</div>
   {project&&<p className="tf-meta"><span>코드 {project.id}</span><span>PM {person(project.pm)}</span>{data?.meetings>0&&<span>회의 {data.meetings}건{data.period.length?` · ${day(data.period[0])} ~ ${day(data.period[1])}`:''}</span>}</p>}
  </div>
  {projects.length>1&&<nav className="tf-projects" aria-label="프로젝트 선택">{projects.map(p=><button key={p.id} className={p.id===projectId?'active':''} aria-current={p.id===projectId?'page':undefined} onClick={()=>onProject(p.id)}><FolderOpen size={15}/><b>{p.name}</b><small>회의 {meetingCount(p.id)}건</small></button>)}</nav>}
  {body}
  {renaming&&project&&<RenameDialog project={project} close={()=>setRenaming(false)} onSaved={p=>{setRenaming(false);onRenamed(p)}}/>}
 </section>;
}
