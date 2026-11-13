const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const {setTimeout:delay}=require('node:timers/promises');
const source=fs.readFileSync(path.join(__dirname,'../portal/production/static/live-sync.js'),'utf8');
function fixture(hidden=false){const window=new EventTarget(),document=new EventTarget();document.hidden=hidden;vm.runInNewContext(source,{window,document,localStorage:{setItem(){}},setTimeout,clearTimeout,Date,Math});return {window,document,start:window.SevlinkLiveSync.start};}
test('serializes requests, retries a protected edit and syncs after a local action',async()=>{
 const f=fixture();let marker='a',active=0,peak=0,applied=0,editing=false,reads=0;
 const live=f.start({interval:15,read:async()=>{active++;peak=Math.max(peak,active);reads++;await delay(20);active--;return {revision:marker};},update:async()=>{if(editing)return false;applied++;await delay(10);return true;}});
 try{
  await delay(100);assert.equal(applied,1);
  editing=true;marker='b';await delay(100);assert.equal(applied,1);
  editing=false;await delay(100);assert.equal(applied,2);
  live.nudge();await delay(160);assert.equal(applied,3);
  assert.equal(peak,1);assert.ok(reads>2);
 }finally{live.stop();}
});
test('does not poll hidden pages and stops its timer cleanly',async()=>{
 const f=fixture(true);let reads=0;
 const live=f.start({interval:15,read:async()=>{reads++;return {revision:'a'};},update:async()=>true});
 await delay(60);assert.equal(reads,0);
 f.document.hidden=false;f.document.dispatchEvent(new Event('visibilitychange'));await delay(140);assert.ok(reads>0);
 live.stop();const before=reads;await delay(50);assert.equal(reads,before);
});
