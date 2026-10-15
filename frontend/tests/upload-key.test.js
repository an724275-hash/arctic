import test from 'node:test';
import assert from 'node:assert/strict';
import {uploadKey} from '../src/upload-key.js';

test('a retry reuses the same upload key while a new selection has its own key',()=>{
  const first=new File(['content'],'report.pdf'),second=new File(['content'],'report.pdf');
  assert.equal(uploadKey(first),uploadKey(first));
  assert.notEqual(uploadKey(first),uploadKey(second));
  assert.match(uploadKey(first),/^[0-9a-f-]{36}$/);
});
