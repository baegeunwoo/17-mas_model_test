"""Compare local models on grouping unnumbered meeting minutes by subject.

Reads only the labelled samples in work/v3/agenda_samples (or --samples); never opens
workspace data. Each model runs in its own process so GPU memory is fully released.

  python -m work.v3.benchmark_agenda --check            scorer and samples only, no GPU
  python -m work.v3.benchmark_agenda --models all       every downloaded candidate
  python -m work.v3.benchmark_agenda --models qwen3-14b,qwen3-32b --think

Scores (pairs of lines, 1.0 is perfect):
  회의 안 묶기  lines of one meeting that belong together are grouped together
  회의 간 연결  the same subject in different meetings gets the same topic ID
Lines labelled meta (header rows) and etc (greetings, no subject) are not scored.
Results: data/agenda-benchmark/<time>/report.md
"""
import argparse, json, os, subprocess, sys, time
from collections import Counter
from datetime import datetime
from itertools import combinations
from pathlib import Path

SERVICE=Path(__file__).resolve().parents[2]
SAMPLES=Path(__file__).with_name('agenda_samples')
RESULTS=SERVICE/'data'/'agenda-benchmark'
MODEL_DIR=SERVICE.parent/'b2-model'
SKIP=('meta','etc')


def catalog():
    if str(MODEL_DIR) not in sys.path:sys.path.insert(0,str(MODEL_DIR))
    import model_catalog
    return model_catalog


def line_id(index):
    return f'L{index+1:03d}'


def load_samples(folder=SAMPLES):
    from work.v3.agenda_ai import is_meta
    projects=[]
    for path in sorted(Path(folder).glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        for m in data['meetings']:
            for label,text in m['lines']:
                if label not in SKIP and label not in data['topics']:
                    raise ValueError(f'{path.name}: 정답 표시 {label} 이(가) topics에 없습니다.')
                # The app drops header rows before grouping; the answer must agree.
                if (label=='meta')!=is_meta(text):
                    raise ValueError(f'{path.name}: "{text}" 은(는) 머리 정보 행 판단과 정답 표시(meta)가 다릅니다.')
        projects.append({**data,'file':path.name})
    if not projects:raise ValueError(f'{folder} 에 테스트 회의록(.json)이 없습니다.')
    return projects


def meeting_lines(meeting):
    return [{'id':line_id(i),'text':text} for i,(_,text) in enumerate(meeting['lines'])]


def run_project(project,generate,count=None,thinking=False,on_meeting=None):
    """Same order and topic hand-over as the app: each meeting sees earlier subjects."""
    from work.v3.agenda_ai import group_meeting,project_topics
    outputs=[]
    for i,m in enumerate(project['meetings']):
        topics=project_topics([{'date':o['date'],'created_at':str(k),'agendas':o['agendas']} for k,o in enumerate(outputs)])
        started=time.perf_counter()
        try:agendas,metrics=group_meeting(generate,meeting_lines(m),topics,count,thinking=thinking);error=''
        except Exception as exc:agendas,metrics,error=[],{},f'{type(exc).__name__}: {exc}'[:300]
        outputs.append({'title':m['title'],'date':m['date'],'agendas':agendas,'metrics':metrics,'error':error,'seconds':round(time.perf_counter()-started,2)})
        if on_meeting:on_meeting(i,outputs[-1])
    return outputs


def assignments(project,outputs):
    gold={};pred={}
    for i,(m,out) in enumerate(zip(project['meetings'],outputs)):
        where={}
        for g in out['agendas']:
            for ref in g['lines']:where[ref]=g['topic_id'] or f'misc:{i}'
        for j,(label,_) in enumerate(m['lines']):
            if label in SKIP:continue
            key=(i,line_id(j));gold[key]=label
            pred[key]=where.get(key[1],f'none:{i}:{j}')   # an unplaced line stands alone
    return gold,pred


def pair_counts(gold,pred):
    counts={'within':[0,0,0],'cross':[0,0,0]}   # same subject: [both, only predicted, only gold]
    for a,b in combinations(gold,2):
        same_gold=gold[a]==gold[b];same_pred=pred[a]==pred[b]
        bucket=counts['within' if a[0]==b[0] else 'cross']
        if same_gold and same_pred:bucket[0]+=1
        elif same_pred:bucket[1]+=1
        elif same_gold:bucket[2]+=1
    return counts


def f1(counts):
    both,only_pred,only_gold=counts
    precision=both/(both+only_pred) if both+only_pred else 1.0
    recall=both/(both+only_gold) if both+only_gold else 1.0
    return {'precision':round(precision,3),'recall':round(recall,3),'f1':round(2*precision*recall/(precision+recall),3) if precision+recall else 0.0}


def score(projects,runs):
    total={'within':[0,0,0],'cross':[0,0,0]};per_project=[];count_error=[]
    for project,outputs in zip(projects,runs):
        gold,pred=assignments(project,outputs);counts=pair_counts(gold,pred)
        for k in total:total[k]=[x+y for x,y in zip(total[k],counts[k])]
        per_project.append({'project':project['project'],'within':f1(counts['within']),'cross':f1(counts['cross'])})
        for m,out in zip(project['meetings'],outputs):
            gold_topics={label for label,_ in m['lines'] if label not in SKIP}
            count_error.append(abs(len([g for g in out['agendas'] if g['topic_id']])-len(gold_topics)))
    within,cross=f1(total['within']),f1(total['cross'])
    return {'within':within,'cross':cross,'score':round((within['f1']+cross['f1'])/2,3),'topic_count_error':round(sum(count_error)/max(1,len(count_error)),2),'projects':per_project}


def baseline_runs(projects,kind):
    """Reference points for reading scores: the exact answer and 'one group per meeting'."""
    runs=[]
    for p in projects:
        outputs=[]
        for i,m in enumerate(p['meetings']):
            if kind=='oracle':
                groups={}
                for j,(label,_) in enumerate(m['lines']):
                    if label not in SKIP:groups.setdefault(label,[]).append(line_id(j))
                agendas=[{'topic_id':label,'title':p['topics'][label],'lines':ids} for label,ids in groups.items()]
            else:
                agendas=[{'topic_id':f'meeting-{i}','title':m['title'],'lines':[line_id(j) for j,(label,_) in enumerate(m['lines']) if label!='meta']}]
            outputs.append({'title':m['title'],'date':m['date'],'agendas':agendas,'metrics':{},'error':'','seconds':0})
        runs.append(outputs)
    return runs


def summary_row(name,result,scores):
    meetings=[o for run in result['runs'] for o in run]
    generated=sum(o['metrics'].get('output_tokens',0) for o in meetings)
    gen_seconds=sum(o['metrics'].get('generation_seconds',0) for o in meetings)
    return {'name':name,'label':result.get('label',''),'score':scores['score'],'within':scores['within']['f1'],'cross':scores['cross']['f1'],
            'failures':sum(1 for o in meetings if o['error']),'meetings':len(meetings),
            'seconds_per_meeting':round(sum(o['seconds'] for o in meetings)/max(1,len(meetings)),1),
            'tokens_per_second':round(generated/gen_seconds,1) if gen_seconds else None,
            'peak_vram_gb':result.get('peak_vram_gb'),'load_seconds':result.get('load_seconds'),'topic_count_error':scores['topic_count_error']}


def table(rows):
    head='| 모델 | 종합 | 회의 안 묶기 | 회의 간 연결 | 주제 수 오차 | 실패 | 회의당 초 | 토큰/초 | 최대 GPU 메모리 | 로딩 초 |\n|---|---|---|---|---|---|---|---|---|---|\n'
    show=lambda v,suffix='':'-' if v is None else f'{v}{suffix}'
    return head+''.join(f"| {r['name']} | **{r['score']}** | {r['within']} | {r['cross']} | {r['topic_count_error']} | {r['failures']}/{r['meetings']} | {show(r['seconds_per_meeting'])} | {show(r['tokens_per_second'])} | {show(r['peak_vram_gb'],' GB')} | {show(r['load_seconds'])} |\n" for r in rows)


def detail(projects,result):
    """Per meeting: each predicted group with the correct subject of every line."""
    out=[]
    for p,outputs in zip(projects,result['runs']):
        out.append(f"\n## {p['project']}\n")
        names={}
        for i,(m,o) in enumerate(zip(p['meetings'],outputs)):
            out.append(f"\n### {i+1}. {m['title']} ({m['date']})\n")
            if o['error']:out.append(f"- 실패: {o['error']}\n");continue
            labels={line_id(j):label for j,(label,_) in enumerate(m['lines'])};texts={line_id(j):t for j,(_,t) in enumerate(m['lines'])}
            for g in o['agendas']:
                linked=g['topic_id'] in names
                if g['topic_id'] and not linked:names[g['topic_id']]=g['title']
                scored=[labels[x] for x in g['lines'] if labels[x] not in SKIP]
                major=Counter(scored).most_common(1)[0][0] if scored else None
                tag='이전 회의 주제에 연결' if linked else '기타' if not g['topic_id'] else '새 주제'
                out.append(f"- **{g['title']}** ({tag}{', 정답: '+p['topics'][major] if major else ''})\n")
                for x in g['lines']:
                    label=labels[x];mark='' if label in SKIP or label==major else f" ✗ 정답: {p['topics'][label]}"
                    out.append(f"  - {x} {texts[x]}{mark}\n")
    return ''.join(out)


def worker(key,out,thinking,samples):
    """Runs inside a fresh process for one model."""
    os.environ['B2_MODEL']=key
    import torch
    from work.v3.agenda_ai import model_generate
    projects=load_samples(samples)
    started=time.perf_counter();generate,count,spec=model_generate(MODEL_DIR);load_seconds=round(time.perf_counter()-started,1)
    print(f'[{key}] 모델 로딩 {load_seconds}초 · {torch.cuda.get_device_name(0)}',flush=True)
    def progress(project):
        def report(i,o):
            state='실패: '+o['error'] if o['error'] else f"주제 {len(o['agendas'])}개"
            print(f"[{key}{' 생각' if thinking else ''}] {project['file']} {i+1}/{len(project['meetings'])} · {o['seconds']}초 · {state}",flush=True)
        return report
    runs=[run_project(p,generate,count,thinking,progress(p)) for p in projects]
    result={'key':key,'label':spec['label'],'thinking':thinking,'gpu':torch.cuda.get_device_name(0),'load_seconds':load_seconds,
            'peak_vram_gb':round(torch.cuda.max_memory_allocated()/1e9,1),'runs':runs}
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')


def main():
    try:sys.stdout.reconfigure(errors='replace')
    except AttributeError:pass
    parser=argparse.ArgumentParser(description='회의록 주제 묶기 모델 비교')
    parser.add_argument('--models',default='all',help='all 또는 쉼표로 구분한 모델 키')
    parser.add_argument('--think',action='store_true',help='생각 모드를 지원하는 모델은 생각 모드로도 한 번 더 실행')
    parser.add_argument('--samples',default=str(SAMPLES),help='테스트 회의록 폴더')
    parser.add_argument('--check',action='store_true',help='GPU 없이 테스트 회의록과 채점만 확인')
    parser.add_argument('--worker');parser.add_argument('--out');parser.add_argument('--thinking',action='store_true')
    args=parser.parse_args()
    if args.worker:return worker(args.worker,args.out,args.thinking,args.samples)
    projects=load_samples(args.samples)
    lines=sum(1 for p in projects for m in p['meetings'] for label,_ in m['lines'] if label not in SKIP)
    print(f"테스트 회의록: 프로젝트 {len(projects)}개, 회의 {sum(len(p['meetings']) for p in projects)}건, 채점 대상 {lines}행",flush=True)
    rows=[];details=[]
    for kind,name in (('oracle','(참고) 정답 그대로'),('single','(참고) 회의마다 한 묶음')):
        result={'runs':baseline_runs(projects,kind)};rows.append(summary_row(name,result,score(projects,result['runs'])))
    if args.check:
        print(table(rows));return 0
    models=catalog()
    keys=list(models.MODELS) if args.models=='all' else [k.strip() for k in args.models.split(',') if k.strip()]
    unknown=[k for k in keys if k not in models.MODELS]
    if unknown:raise SystemExit('알 수 없는 모델: '+', '.join(unknown)+' / 사용 가능: '+', '.join(models.MODELS))
    missing=[k for k in keys if not models.is_downloaded(k)]
    for k in missing:print(f'건너뜀: {k} 모델 파일이 없습니다. 06_선택_비교모델다운로드.cmd 또는 download_models.py --model {k}',flush=True)
    jobs=[(k,False) for k in keys if k not in missing]
    if args.think:jobs+=[(k,True) for k in keys if k not in missing and models.MODELS[k]['hybrid_thinking']]
    if not jobs:raise SystemExit('실행할 모델이 없습니다.')
    folder=RESULTS/datetime.now().strftime('%Y%m%d-%H%M%S');folder.mkdir(parents=True,exist_ok=True)
    for key,thinking in jobs:
        name=key+(' (생각 모드)' if thinking else '');raw=folder/f"{key}{'-think' if thinking else ''}.json"
        command=[sys.executable,'-m','work.v3.benchmark_agenda','--worker',key,'--out',str(raw),'--samples',args.samples]+(['--thinking'] if thinking else [])
        print(f'\n=== {name} 실행 ===',flush=True)
        done=subprocess.run(command,cwd=SERVICE,env={**os.environ,'B2_MODEL':key,'PYTHONUTF8':'1'})
        if done.returncode or not raw.is_file():
            print(f'{name}: 실행 실패(종료 코드 {done.returncode}). 위 메시지를 확인해 주세요.',flush=True)
            rows.append({'name':name,'label':'','score':0.0,'within':0.0,'cross':0.0,'failures':'실행 실패','meetings':'-','seconds_per_meeting':None,'tokens_per_second':None,'peak_vram_gb':None,'load_seconds':None,'topic_count_error':'-'});continue
        result=json.loads(raw.read_text(encoding='utf-8'));scores=score(projects,result['runs'])
        result['scores']=scores;raw.write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
        rows.append(summary_row(name,result,scores));details.append((name,result))
    # The app never uses thinking mode, so only direct runs are recommended for it.
    ranked=[r for r in rows if not r['name'].startswith('(참고)') and isinstance(r['failures'],int) and '생각' not in r['name']]
    best=max(ranked,key=lambda r:(r['score'],-(r['seconds_per_meeting'] or 0)),default=None)
    gpu=next((r['gpu'] for _,r in details if r.get('gpu')),'')
    report=[f"# 회의록 주제 묶기 모델 비교\n\n{datetime.now():%Y-%m-%d %H:%M} · {gpu} · 테스트 회의록 {args.samples}\n\n",table(rows),
            '\n종합 = (회의 안 묶기 + 회의 간 연결) / 2. 1.0이 정답과 같습니다. 주제 수 오차는 회의당 주제 개수 차이의 평균입니다.\n']
    if best:report.append(f"\n앱에서 쓸 수 있는 모델 중 가장 높은 점수: **{best['name']}** ({best['score']}). 앱에 쓰려면 b2-service/.env 에 B2_MODEL={best['name']} 을 넣고 서비스를 다시 실행합니다. 생각 모드 결과는 참고용입니다(앱은 생각 모드를 쓰지 않습니다).\n")
    for name,result in details:report.append(f'\n---\n\n# {name} 상세\n'+detail(projects,result))
    (folder/'report.md').write_text(''.join(report),encoding='utf-8')
    print('\n'+table(rows));print(f'결과: {folder/"report.md"}')
    return 0


if __name__=='__main__':raise SystemExit(main())
