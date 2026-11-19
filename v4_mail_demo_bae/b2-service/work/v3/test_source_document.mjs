import {minutesLayout} from './source_document.js';
const eq=(a,b,msg)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw new Error((msg||'')+' '+JSON.stringify(a)+' !== '+JSON.stringify(b))};
const L=texts=>texts.map((text,i)=>({id:'L'+String(i+1).padStart(3,'0'),text}));

// "key: value" header, numbered sections, nested bullets, closing sentence.
let r=minutesLayout(L(['회의명: 킥오프','일시: 2026-08-26 10:00','장소: 회의실 B','참석자: 장현우 / 김양일','1. 장비 개요','  - 적층 속도 0.5초','2. 일정','- 3월 말 셋업','다음 회의는 9월 9일.']));
eq(r.header.title.value,'킥오프');eq(r.header.place.value,'회의실 B');eq(r.header.attendees.id,'L004');
eq(r.agenda,['장비 개요','일정']);
eq(r.blocks.map(b=>[b.type,b.depth??'']),[['heading',''],['item',1],['heading',''],['item',0],['text','']]);

// "key | value" header followed by a table with its own column header.
r=minutesLayout(L(['회의명 | 제박기 협의','일시 | 2026-09-03','항목 | 협의 내용 | 담당','두께 | 6 µm | 동진','폭 | 1,400 mm | -']));
eq(r.header.date.value,'2026-09-03');eq(r.blocks.length,1);
eq(r.blocks[0].head,true);eq(r.blocks[0].rows.map(x=>x.cells[0]),['항목','두께','폭']);

// Speaker lines are body text, not header fields; a header word later in the body stays in the body.
r=minutesLayout(L(['회의명: 2차','진효창: 견적이 40% 비쌉니다.','■ 결정','· 레이저 노칭','장소: 본문 속 문장']));
eq(Object.keys(r.header),['title']);eq(r.blocks.map(b=>b.type),['text','heading','item','text']);eq(r.agenda,['결정']);

// Every non-header line is kept, with its original id.
const src=L(['회의명: x','a','b | c','[미결 사항]','  · d']);
r=minutesLayout(src);
const ids=r.blocks.flatMap(b=>b.rows?b.rows.map(x=>x.id):[b.id]);
eq(ids,['L002','L003','L004','L005']);
console.log('source_document ok');
