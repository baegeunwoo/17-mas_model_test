"""Subject grouping: validation, scoring and the analysis hand-over. No real model is loaded."""
import json, os, tempfile
os.environ['B2_TEAM_TESTING']='1'
os.environ.setdefault('B2_TEAM_DATA_DIR',tempfile.mkdtemp(prefix='b2-v3-agenda-tests-'))
from fastapi.testclient import TestClient
from work.v3.server import app, legacy as w
from work.v3 import agenda_ai, benchmark_agenda
import work.v3.fast_ai
import pytest

LINES=[{'id':'L001','text':'회의명: 테스트'},{'id':'L002','text':'라인 속도는 60 m/min으로 한다.'},{'id':'L003','text':'납기는 2월 첫째 주다.'},
       {'id':'L004','text':'속도 80 m/min 여유를 검토한다.'},{'id':'L005','text':'그 건은 다음 주에 확인한다.'},{'id':'L006','text':'다음 회의는 화요일이다.'}]
TOPICS=[{'id':'Tspeed','title':'라인 속도','date':'2026-09-01','sample':''},{'id':'Tdelivery','title':'납기','date':'','sample':''}]


@pytest.mark.parametrize('folder',[benchmark_agenda.SAMPLES,benchmark_agenda.SAMPLES.with_name('agenda_samples_2')])
def test_samples_and_scoring_reference_points(folder):
    projects=benchmark_agenda.load_samples(folder)
    assert len(projects)==3 and sum(len(p['meetings']) for p in projects)==10
    exact=benchmark_agenda.score(projects,benchmark_agenda.baseline_runs(projects,'oracle'))
    single=benchmark_agenda.score(projects,benchmark_agenda.baseline_runs(projects,'single'))
    assert exact['score']==1.0 and exact['topic_count_error']==0
    assert single['cross']['f1']==0.0 and single['within']['recall']==1.0 and single['score']<0.3
    # Every sample project carries at least one subject into a later meeting.
    for p in projects:
        seen=[{label for label,_ in m['lines']} for m in p['meetings']]
        assert any(seen[i]&seen[j]-{'meta','etc'} for i in range(len(seen)) for j in range(i+1,len(seen)))


def test_normalize_links_known_subjects_and_keeps_every_line():
    result=agenda_ai.normalize({'agendas':[['Tspeed','속도',['L001','L002','L004-L005']],[None,'납기',['L003','L002']],['Tunknown','도장',['L999']]]},LINES,TOPICS)
    assert [g['topic_id'] for g in result]==['Tspeed','Tdelivery',None]   # same name as an earlier subject links to it
    assert result[0]['lines']==['L002','L004','L005']                      # header row dropped, range expanded
    assert result[1]['lines']==['L003']                                     # a line belongs to one subject only
    assert result[2]=={'topic_id':None,'title':'기타','lines':['L006'],'sample':'다음 회의는 화요일이다.'}
    for bad in ({'agendas':'x'},{'items':[]},{'agendas':[['a','b']]},{'agendas':[[None,'',['L002']]]}):
        with pytest.raises(ValueError):agenda_ai.normalize(bad,LINES,TOPICS)
    assert agenda_ai.parse('<think>{"x":1}</think>{"agendas":[]}')=={'agendas':[]}


def test_long_meeting_is_split_and_subjects_carry_over():
    def generate(prompt,budget,thinking):
        data=json.loads(prompt[1]['content']);known=data['existing_topics']
        return json.dumps({'agendas':[[known[0][0] if known else None,'라인 속도',[x[0] for x in data['lines']]]]}),{'output_tokens':3,'seconds':.1}
    rows=[{'id':f'L{i:03d}','text':f'속도 이야기 {i}'} for i in range(1,41)]
    groups,metrics=agenda_ai.group_meeting(generate,rows,[],count_tokens=lambda p:len(json.loads(p[1]['content'])['lines'])*100,max_input_tokens=1500)
    assert len(groups)==1 and len(groups[0]['lines'])==40 and metrics['split'] and metrics['passes']==4
    with pytest.raises(ValueError):agenda_ai.group_meeting(lambda *a:('{"agendas":[',{'hit_limit':True}),rows,[])


def test_tests_never_load_a_model_unless_asked(monkeypatch):
    monkeypatch.delenv('B2_AGENDA_GROUPING',raising=False)
    assert not agenda_ai.enabled()
    monkeypatch.setenv('B2_AGENDA_GROUPING','1');assert agenda_ai.enabled()


class Queue:
    def __init__(self):self.jobs=[]
    def submit(self,*args):self.jobs.append(args)


@pytest.fixture
def client(monkeypatch):
    queue=Queue();monkeypatch.setattr(w,'POOL',queue);monkeypatch.setattr(w,'PREVIEW_POOL',Queue())
    monkeypatch.setenv('B2_AGENDA_GROUPING','1')
    with TestClient(app,headers={'X-B2-Request':'workspace'}) as c:
        assert c.post('/api/demo-login',json={'username':'team1'}).status_code==200
        with w.connect() as db:before={(r['kind'],r['id']) for r in db.execute('SELECT kind,id FROM records')}
        yield c,queue
        # Test modules share one database; leave nothing behind for the others.
        with w.connect() as db:
            for kind,ident in {(r['kind'],r['id']) for r in db.execute('SELECT kind,id FROM records')}-before:
                db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,ident))


def register(c,p,body,date):
    content=f'프로젝트: {p["name"]}\n회의명: {date} 협의\n회의일: {date}\n{body}'
    item=c.post('/api/v3/imports',files=[('files',(date+'.txt',content.encode(),'text/plain'))]).json()['items'][0]
    result=c.post('/api/v3/register',json={'items':[{'id':item['id'],'project_id':p['id'],'date':date}]})
    assert result.status_code==202,result.text
    return result.json()['registered'][0]['id']


def test_analysis_stores_subjects_and_links_them_across_meetings(client,monkeypatch):
    c,queue=client
    monkeypatch.setattr(work.v3.fast_ai,'extract',lambda w,rows,topics,on_phase=None:({'summary':[],'decisions':[],'items':[]},{'items':[]},{'model':'controlled-test'}))
    offered=[]
    def generate(prompt,budget,thinking):
        data=json.loads(prompt[1]['content']);known={t[1]:t[0] for t in data['existing_topics']};offered.append(data['existing_topics'])
        groups={}
        for ref,text in data['lines']:
            if text.startswith(('프로젝트','회의명','회의일')):continue
            title='라인 속도' if '속도' in text else '납기' if ('납기' in text or '출하' in text) else '기타'
            groups.setdefault(title,[]).append(ref)
        return json.dumps({'agendas':[[known.get(t),t,ids] for t,ids in groups.items()]},ensure_ascii=False),{'output_tokens':10,'seconds':.1}
    monkeypatch.setattr(agenda_ai,'model_generate',lambda model_dir:(generate,None,{'label':'controlled-test'}))
    p=c.post('/api/projects',json={'name':'주제 묶기 검증','members':['team1','team2']}).json()
    first=register(c,p,'라인 속도는 60 m/min으로 시작한다.\n납기는 2월 둘째 주다.\n속도는 80까지 여유를 둔다.','2026-09-02')
    fn,*args=queue.jobs.pop();fn(*args)
    second=register(c,p,'출하는 2월 첫째 주로 당긴다.\n최고 속도 80 m/min으로 확정했다.','2026-09-16')
    fn,*args=queue.jobs.pop();fn(*args)
    with w.connect() as db:
        a,b=w.read(db,'meeting',first),w.read(db,'meeting',second)
    assert a['analysis_state']=='ready' and b['analysis_state']=='ready' and not a['agenda_error'] and not b['agenda_error']
    speed_a=next(g for g in a['agendas'] if g['title']=='라인 속도');speed_b=next(g for g in b['agendas'] if g['title']=='라인 속도')
    assert len(speed_a['lines'])==2 and speed_b['topic_id']==speed_a['topic_id']   # linked across meetings
    assert next(g for g in b['agendas'] if g['title']=='납기')['topic_id']==next(g for g in a['agendas'] if g['title']=='납기')['topic_id']
    assert {t[1] for t in offered[-1]}>={'라인 속도','납기'}
    assert c.get('/api/meetings/'+second).json()['agendas']==b['agendas']   # visible for inspection
    # A grouping failure never fails the meeting analysis.
    monkeypatch.setattr(agenda_ai,'model_generate',lambda model_dir:(lambda *x:('응답 없음',{}),None,{'label':'controlled-test'}))
    assert c.post(f'/api/v3/meetings/{second}/analyze').status_code==202
    fn,*args=queue.jobs.pop();fn(*args)
    with w.connect() as db:b=w.read(db,'meeting',second)
    assert b['analysis_state']=='ready' and b['agendas']==[] and b['agenda_error']


def test_project_topic_flow_links_meetings_and_changes():
    from work.v3.topic_flow import project_flow
    lines=lambda *t:[{'id':f'L{i+1:03}','text':x} for i,x in enumerate(t)]
    m1={'id':'m1','title':'1차','date':'2026-09-01','revision':1,'agenda_revision':1,'lines':lines('속도 60 m/min','납기 2월'),
        'agendas':[{'topic_id':'Tspeed','title':'속도','lines':['L001']},{'topic_id':'Tdel','title':'납기','lines':['L002']}]}
    m2={'id':'m2','title':'2차','date':'2026-10-01','revision':2,'agenda_revision':1,'lines':lines('라인 속도 80으로 변경 요청','기타 안내'),
        'agendas':[{'topic_id':'Tspeed','title':'라인 속도','lines':['L001']},{'topic_id':None,'title':'기타','lines':['L002']}]}
    gone={'id':'m3','title':'삭제','date':'2026-11-01','deleted_at':'x','lines':lines('속도'),'agendas':[{'topic_id':'Tspeed','title':'속도','lines':['L001']}]}
    es=[{'id':'e1','meeting_id':'m1','source_revision':1,'title':'라인 속도','category':'사양','before':'','after':'60 m/min','business_state':'확정','evidence':['L001']},
        {'id':'e2','meeting_id':'m2','source_revision':2,'title':'라인 속도','category':'사양','before':'60 m/min','after':'80 m/min','business_state':'요청','evidence':['L001']},
        {'id':'e3','meeting_id':'m2','source_revision':1,'title':'옛 기록','category':'사양','before':'','after':'x','business_state':'요청','evidence':['L001']}]
    r=project_flow([m2,gone,m1],es)
    assert [t['id'] for t in r['topics']]==['Tspeed','Tdel'] and r['meetings']==2
    speed=r['topics'][0]
    assert speed['title']=='라인 속도' and speed['first']['meeting_id']=='m1' and speed['last']['meeting_id']=='m2'
    assert [s['lines'][0]['text'] for s in speed['steps']]==['속도 60 m/min','라인 속도 80으로 변경 요청']
    assert [c['id'] for s in speed['steps'] for c in s['changes']]==['e1','e2']      # old revision record left out
    assert speed['current']['after']=='80 m/min' and [o['after'] for o in speed['open']]==['80 m/min']
    assert speed['steps'][1]['stale'] and not speed['steps'][0]['stale']
    assert r['topics'][1]['current'] is None and r['topics'][1]['open']==[]


def test_project_subject_hint_from_meeting_titles():
    from work.v3.topic_flow import common_subject
    assert common_subject(['동진 제박기 3호기 사양 협의','제박기 3호기 사양 확정 회의','제박기 3호기 2차 협의'])=='제박기 3호기'
    assert common_subject(['한 건뿐인 회의'])=='' and common_subject(['가 회의','나 회의'])==''


def test_project_topic_status():
    from work.v3.topic_flow import project_flow
    L=lambda t:[{'id':'L001','text':t}]
    m=lambda i,d,tid:{'id':i,'title':i,'date':d,'revision':1,'lines':L('x'),'agendas':[{'topic_id':tid,'title':tid,'lines':['L001']}]}
    e=lambda i,mid,state:{'id':i,'meeting_id':mid,'source_revision':1,'title':'값','category':'사양','before':'','after':state,'business_state':state,'evidence':['L001']}
    r={t['id']:t['status'] for t in project_flow([m('a','2026-01-01','Tdone'),m('b','2026-02-01','Tdone'),m('c','2026-01-01','Tone'),m('d','2026-01-01','Tgo'),m('f','2026-02-01','Tgo')],
       [e('1','a','요청'),e('2','b','확정'),e('3','d','요청'),e('4','f','보류')])['topics']}
    assert r=={'Tdone':'완료','Tone':'최초','Tgo':'진행중'}
