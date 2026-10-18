'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const BASE='e35c349d269743cc7cd7f8bc199e09470807fe86';
function read(path,blob){
 const bytes=cp.execFileSync('git',['show',BASE+':'+path],{timeout:30000,maxBuffer:20000000});
 const input=Buffer.concat([Buffer.from('blob '+bytes.length+String.fromCharCode(0)),bytes]);
 assert.equal(crypto.createHash('sha1').update(input).digest('hex'),blob);
 return bytes.toString('utf8');
}
function literal(src,key,end){
 const start=src.indexOf(key); assert.ok(start>=0,key);
 const stop=src.indexOf(end,start+key.length);assert.ok(stop>start,key);
 return new Function('return ('+src.slice(start+key.length,stop+end.length-1)+')')();
}
test('frozen 25 records get three different source hashes depending on config',async()=>{
 const html=read('CardioOracle.html','a52f055dae8c5f672b9d8498f7e79e966458e414');
 const archive=JSON.parse(read('prospective_predictions_20260325.json','d61e874de348d8840317417848b51514ae272c8f'));
 assert.ok(html.includes("params.get('config') ?? 'cardiorenal'"));
 assert.ok(html.includes('const TRAINING_DATA = DATA_LIBRARY[window._configKey].training'));
 const library=literal(html,'const DATA_LIBRARY = ','\n};');
 const seeds=literal(html,'const SEED_PREDICTIONS = ','\n];');
 assert.equal(seeds.length,25);assert.equal(archive.trials.length,25);
 const lines=html.split('\n');
 const impl=lines.slice(4689,4706).join('\n')+'\n'
   +lines.slice(4737,4751).join('\n')+'\n'
   +lines.slice(4754,4802).join('\n')+'\n'
   +'return {pvSeedIfNeeded,pvGetCohort,pvComputeEntryHash};';
 const build=new Function('TRAINING_DATA','SEED_PREDICTIONS','sha256Hex','PV_KEYS','PV_MODEL_VERSION','localStorage',impl);
 const digest=async str=>crypto.createHash('sha256').update(str,'utf8').digest('hex');
 const rows=[];
 for(const config of ['cardiorenal','cad','af']){
   const storage=new Map();
   const localStorage={getItem:k=>storage.has(k)?storage.get(k):null,
      setItem:(k,v)=>storage.set(k,String(v))};
   const app=build(library[config].training,seeds,digest,
     {cohort:'cardiooracle_pv_cohort',seeded:'cardiooracle_pv_seeded'},'cardiooracle_v1.0',localStorage);
   await app.pvSeedIfNeeded();
   const rs=app.pvGetCohort();
   assert.equal(rs.length,25);
   assert.equal(storage.get('cardiooracle_pv_seeded'),'1');
   const expected=await digest(JSON.stringify(library[config].training.trials));
   assert.ok(rs.every(r=>r.training_hash===expected));
   let prev=null;
   for(let i=0;i<25;i++){
     const x=rs[i];
     assert.equal(x.seq,i+1);
     assert.equal(x.nct_id,archive.trials[i].nct_id);
     assert.equal(x.prediction.p_ensemble,archive.trials[i].prediction.p_success);
     assert.equal(x.prev_hash,prev);
     assert.equal(x.entry_hash,await app.pvComputeEntryHash(x,prev));
     prev=x.entry_hash;
   }
   rows.push({config,n:library[config].training.trials.length,
     training:expected,first:rs[0].entry_hash,last:rs[24].entry_hash,
     predictions:rs.map(x=>x.prediction.p_ensemble).join(',')});
 }
 assert.deepEqual(rows.map(x=>x.n),[784,90,28]);
 assert.equal(new Set(rows.map(x=>x.predictions)).size,1);
 assert.equal(new Set(rows.map(x=>x.training)).size,3);
 assert.equal(new Set(rows.map(x=>x.first)).size,3);
 assert.equal(new Set(rows.map(x=>x.last)).size,3);
});
