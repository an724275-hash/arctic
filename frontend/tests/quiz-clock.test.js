import test from 'node:test';
import assert from 'node:assert/strict';
import {createQuizClock} from '../src/quiz-clock.js';

const attempt = (remaining, id='attempt-one') => ({id, status:'active', expires_at:'2026-10-15T10:10:00Z', server_now:new Date(Date.parse('2026-10-15T10:10:00Z')-remaining).toISOString()});

test('a slow answer response does not add time to an active attempt',()=>{
  let time=0;
  const clock=createQuizClock(()=>time);
  clock.sync(attempt(600000),0);
  time=10000;
  clock.sync(attempt(591000),8000);
  assert.equal(clock.deadline,600000);
  time=20000;
  clock.sync(attempt(579000),18000);
  assert.equal(clock.deadline,598000);
});

test('device clock changes do not affect an established deadline',()=>{
  let time=1000;
  const clock=createQuizClock(()=>time);
  clock.sync(attempt(600000),1000);
  const original=Date.now;
  try{
    Date.now=()=>original()+3600000;
    time=2000;
    clock.sync(attempt(599000),2000);
    assert.equal(clock.deadline-time,599000);
  }finally{Date.now=original;}
});

test('a resumed attempt accounts for latency and a new attempt gets its own deadline',()=>{
  let time=4000;
  const clock=createQuizClock(()=>time);
  assert.equal(clock.sync(attempt(30000),0),32000);
  time=5000;
  assert.equal(clock.sync({...attempt(20000),status:'expired'},5000),5000);
  assert.equal(clock.sync(attempt(600000,'attempt-two'),5000),605000);
});
