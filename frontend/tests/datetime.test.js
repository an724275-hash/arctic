import test from 'node:test';
import assert from 'node:assert/strict';
import {localDateTime} from '../src/datetime.js';

test('editing an unchanged meeting time preserves its UTC instant in different zones',()=>{
  const original=process.env.TZ;
  try{
    for(const [zone,expected] of [['Asia/Yakutsk','2030-01-15T09:30'],['Europe/Moscow','2030-01-15T03:30'],['UTC','2030-01-15T00:30'],['America/New_York','2030-01-14T19:30']]){
      process.env.TZ=zone;
      const value=localDateTime('2030-01-15T00:30:00Z');
      assert.equal(value,expected,zone);
      assert.equal(new Date(value).toISOString(),'2030-01-15T00:30:00.000Z',zone);
    }
  }finally{if(original===undefined)delete process.env.TZ;else process.env.TZ=original;}
  assert.equal(localDateTime(null),'');
  assert.equal(localDateTime('invalid'),'');
});
