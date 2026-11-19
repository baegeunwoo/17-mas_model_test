import assert from 'node:assert/strict';
import {agendaView} from './agenda_topics.js';
const lines=[{id:'L001',text:'회의명: 2차'},{id:'L002',text:'  - 납기는 2월 첫째 주'},{id:'L003',text:'속도 80 m/min 검토'},{id:'L004',text:'다음 회의는 화요일'}];
const first={id:'a',project_id:'p',title:'1차',date:'2026-09-02',agendas:[{topic_id:'Tdel',title:'납기',lines:['L002']}]};
const later={id:'c',project_id:'p',title:'3차',date:'2026-10-07',agendas:[{topic_id:'Tspeed',title:'속도',lines:['L005']}]};
const other={id:'x',project_id:'q',title:'다른 프로젝트',date:'2026-09-01',agendas:[{topic_id:'Tdel',title:'납기',lines:[]}]};
const meeting={id:'b',project_id:'p',title:'2차',date:'2026-09-16',revision:2,agenda_revision:2,lines,
 agendas:[{topic_id:null,title:'기타',lines:['L004']},{topic_id:'Tdel',title:'납기',lines:['L002','L999']},{topic_id:'Tspeed',title:'속도',lines:['L003']}]};
const v=agendaView(meeting,[later,meeting,other,first]);
assert.deepEqual(v.groups.map(g=>g.title),['납기','속도','기타']);               // 기타 last
assert.deepEqual(v.groups[0].lines,[{id:'L002',text:'- 납기는 2월 첫째 주'}]);    // original text, unknown IDs dropped
assert.deepEqual(v.groups[0].appearances.map(a=>a.id),['a','b']);               // same project only, by date
assert.ok(v.groups[0].carried&&!v.groups[0].continues);
assert.ok(!v.groups[1].carried&&v.groups[1].continues);
assert.deepEqual(v.groups[2].appearances,[]);
assert.equal(v.topics,2);assert.equal(v.carried,1);assert.equal(v.stale,false);
assert.equal(agendaView({...meeting,agenda_revision:1}).stale,true);
assert.deepEqual(agendaView({id:'n',lines,agendas:[],agenda_error:'모델 없음'}),{groups:[],topics:0,carried:0,stale:false,error:'모델 없음'});
console.log('agenda view ok');
