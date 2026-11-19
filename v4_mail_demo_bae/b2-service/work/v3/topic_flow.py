"""Project-wide subject flow: every subject the analysis linked across meetings (meeting.agendas),
in meeting order, with the original lines and the change records found in those lines.
Read only; no approval state is involved."""

OPEN_STATES=('요청','보류')
GENERIC={'회의','협의','미팅','사양','확정','진행','점검','설계','리뷰','검토','킥오프','결과','보고','회의록','정기','주간','월간'}


def common_subject(titles):
    """Words shared by most meeting titles (e.g. '제박기 3호기'), as a hint next to the project name."""
    titles=[t.split() for t in titles if t]
    if len(titles)<2:return ''
    need=(len(titles)+1)//2
    words=[w for t in titles for w in t if w not in GENERIC and not (w.endswith('차') and w[:-1].isdigit())]
    return ' '.join(w for w in dict.fromkeys(words) if sum(w in t for t in titles)>=max(need,2))


def _when(m):
    return (m.get('date') or '9999-99-99',m.get('created_at') or '')


def visible_changes(meeting,changes):
    """Change records the workspace shows for this meeting's current revision."""
    if meeting.get('analysis_stale'):return []
    return [e for e in changes if e['meeting_id']==meeting['id'] and not e.get('superseded_by_revision')
            and e.get('review_state')!='제외' and e.get('source_revision')==meeting.get('revision')]


def project_flow(meetings,changes):
    meetings=sorted((m for m in meetings if not m.get('deleted_at')),key=_when)
    topics={}
    for m in meetings:
        text={l['id']:l['text'].strip() for l in m.get('lines') or []}
        stale=m.get('agenda_revision') is not None and m.get('agenda_revision')!=m.get('revision')
        found=visible_changes(m,changes)
        for g in m.get('agendas') or []:
            if not g.get('topic_id'):continue   # '기타' is not a subject
            ids=[x for x in g.get('lines') or [] if x in text]
            if not ids:continue
            mine=[{k:e.get(k) for k in ('id','title','category','before','after','business_state','evidence')}
                  for e in found if set(e.get('evidence') or [])&set(ids)]
            t=topics.setdefault(g['topic_id'],{'id':g['topic_id'],'title':g['title'],'steps':[]})
            t['title']=g['title']   # the latest name wins
            t['steps'].append({'meeting_id':m['id'],'title':m['title'],'date':m.get('date') or '','stale':stale,
                               'lines':[{'id':x,'text':text[x]} for x in ids],'changes':mine})
    result=[]
    for t in topics.values():
        steps=t['steps'];latest={}
        for s in steps:
            for e in s['changes']:latest[(e['category'],e['title'])]={**e,'date':s['date'],'meeting_id':s['meeting_id']}
        changes_in_order=[{**e,'date':s['date'],'meeting_title':s['title'],'meeting_id':s['meeting_id']} for s in steps for e in s['changes']]
        current=changes_in_order[-1] if changes_in_order else None
        result.append({**t,'first':_ref(steps[0]),'last':_ref(steps[-1]),'meeting_count':len(steps),
                       'change_count':len(changes_in_order),
                       'current':{k:current[k] for k in ('title','before','after','business_state','date','meeting_title','meeting_id','evidence')} if current else None,
                       'decided':sum(1 for e in changes_in_order if e['business_state']=='확정'),
                       'open':[{'title':e['title'],'after':e['after'],'business_state':e['business_state'],'date':e['date']}
                               for e in latest.values() if e['business_state'] in OPEN_STATES]})
    # Subjects that first came up earlier come first; ties keep the meeting's own order.
    result.sort(key=lambda t:t['first']['date'] or '9999-99-99')
    dates=sorted(m['date'] for m in meetings if m.get('date'))
    return {'topics':result,'meetings':len(meetings),'subject':common_subject([m['title'] for m in meetings]),'period':[dates[0],dates[-1]] if dates else [],
            'multi':sum(1 for t in result if t['meeting_count']>1),'open_topics':sum(1 for t in result if t['open']),
            'grouped':sum(1 for m in meetings if m.get('agendas')),
            'pending':sum(1 for m in meetings if not m.get('agendas'))}


def _ref(step):
    return {'meeting_id':step['meeting_id'],'title':step['title'],'date':step['date']}
