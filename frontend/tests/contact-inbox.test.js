import test from 'node:test';
import assert from 'node:assert/strict';
import {loadContactInbox,contactInbox} from '../src/contact-inbox.js';

const response=body=>new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
const state=()=>({messages:{items:[],total:0},messagesOffset:0,messagesStatus:''});

test('inbox pages use the selected status and keep the correct range',async()=>{
  const c=state();let query;
  globalThis.fetch=async url=>{query=new URL(url,'https://example.com').searchParams;return response({items:[{id:'1',name:'<script>',message:'message',email:'a@example.com',status:'closed',created_at:'2026-10-15'}],total:61});};
  await loadContactInbox(c,60,'closed');
  assert.equal(query.get('offset'),'60');assert.equal(query.get('status'),'closed');
  assert.equal(c.messagesOffset,60);assert.equal(c.messagesStatus,'closed');
  const html=contactInbox(c);assert(html.includes('61–61 из 61'));assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;'));
});

test('a removed last page falls back to the final available page',async()=>{
  const c=state(),offsets=[];
  globalThis.fetch=async url=>{const offset=Number(new URL(url,'https://example.com').searchParams.get('offset'));offsets.push(offset);return response({items:offset===60?[{id:'last'}]:[],total:61});};
  await loadContactInbox(c,90,'new');
  assert.deepEqual(offsets,[90,60]);assert.equal(c.messagesOffset,60);
});

test('a network error leaves the displayed page unchanged',async()=>{
  const c=state();c.messages={items:[{id:'old'}],total:100};
  globalThis.fetch=async()=>{throw new TypeError('offline');};
  await assert.rejects(loadContactInbox(c,30,'closed'));
  assert.equal(c.messagesOffset,0);assert.equal(c.messagesStatus,'');assert.equal(c.messages.items[0].id,'old');
  assert(contactInbox(state()).includes('0–0 из 0'));
});
