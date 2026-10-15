import test from 'node:test';
import assert from 'node:assert/strict';

const makeSession=id=>({user:{id},access_token:`access-${id}`,refresh_token:`refresh-${id}`});
const response=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};};

async function client(fetcher) {
  globalThis.sessionStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
  globalThis.window={dispatchEvent:()=>{throw new Error('a newer session must not be cleared');}};
  globalThis.fetch=fetcher;
  return import(`../src/api.js?test=${Math.random()}`);
}

test('an old private response cannot be used after switching accounts',async()=>{
  const pending=deferred();
  const api=await client(()=>pending.promise);
  api.setSession(makeSession('first'));
  const request=api.request('/users/me');
  api.setSession(makeSession('second'));
  pending.resolve(response({full_name:'private name'}));
  await assert.rejects(request,error=>error.status===409);
  assert.equal(api.getSession().user.id,'second');
});

test('a late unauthorized response does not log out a newer account',async()=>{
  const pending=deferred();
  const api=await client(()=>pending.promise);
  api.setSession(makeSession('first'));
  const request=api.request('/projects');
  api.setSession(makeSession('second'));
  pending.resolve(response({},401));
  await assert.rejects(request,error=>error.status===409);
  assert.equal(api.getSession().user.id,'second');
});

test('switching accounts while reading a private body discards that body',async()=>{
  const body=deferred(),started=deferred();
  const api=await client(()=>Promise.resolve({status:200,ok:true,json:()=>{started.resolve();return body.promise;}}));
  api.setSession(makeSession('first'));
  const request=api.request('/users/me');await started.promise;
  api.setSession(makeSession('second'));body.resolve({full_name:'private name'});
  await assert.rejects(request,error=>error.status===409);
});

test('a delayed refresh cannot replace a newer login',async()=>{
  const pending=deferred(),started=deferred();
  const api=await client(url=>{
    if(url.endsWith('/auth/refresh')){started.resolve();return pending.promise;}
    return Promise.resolve(response({},401));
  });
  api.setSession(makeSession('first'));
  const request=api.request('/projects');
  await started.promise;
  api.setSession(makeSession('second'));
  pending.resolve(response({...makeSession('first'),access_token:'renewed-first'}));
  await assert.rejects(request,error=>error.status===409);
  assert.equal(api.getSession().user.id,'second');
});

test('logout while refreshing cannot restore the old session',async()=>{
  const pending=deferred(),started=deferred();
  const api=await client(url=>{
    if(url.endsWith('/auth/refresh')){started.resolve();return pending.promise;}
    return Promise.resolve(response({},401));
  });
  api.setSession(makeSession('first'));
  const request=api.request('/projects');await started.promise;
  api.setSession(null);pending.resolve(response({...makeSession('first'),access_token:'renewed-first'}));
  await assert.rejects(request,error=>error.status===409);
  assert.equal(api.getSession(),null);
});

test('concurrent expired requests share a refresh and retry with the rotated token',async()=>{
  let refreshes=0;
  const api=await client((url,options)=>{
    if(url.endsWith('/auth/refresh')){
      refreshes++;
      return Promise.resolve(response({...makeSession('first'),access_token:'renewed-first',refresh_token:'rotated-first'}));
    }
    return Promise.resolve(options.headers.Authorization==='Bearer renewed-first'?response({ok:true}):response({},401));
  });
  api.setSession(makeSession('first'));
  const results=await Promise.all([api.request('/projects'),api.request('/notifications')]);
  assert.deepEqual(results,[{ok:true},{ok:true}]);
  assert.equal(refreshes,1);
});

test('a network failure during refresh keeps the session available for retry',async()=>{
  const api=await client(url=>{
    if(url.endsWith('/auth/refresh'))throw new TypeError('Failed to fetch');
    return Promise.resolve(response({},401));
  });
  api.setSession(makeSession('first'));
  await assert.rejects(api.request('/projects'),error=>error.status===0);
  assert.equal(api.getSession().user.id,'first');
});

test('a new account refresh does not wait for the previous account refresh',async()=>{
  const pending=deferred(),started=deferred();
  const api=await client((url,options)=>{
    if(url.endsWith('/auth/refresh')){
      if(JSON.parse(options.body).refresh_token==='refresh-first'){started.resolve();return pending.promise;}
      return Promise.resolve(response({...makeSession('second'),access_token:'renewed-second',refresh_token:'rotated-second'}));
    }
    return Promise.resolve(options.headers.Authorization==='Bearer renewed-second'?response({ok:true}):response({},401));
  });
  api.setSession(makeSession('first'));
  const oldRequest=assert.rejects(api.request('/projects'),error=>error.status===409);
  await started.promise;
  api.setSession(makeSession('second'));
  assert.deepEqual(await api.request('/notifications'),{ok:true});
  pending.resolve(response({...makeSession('first'),access_token:'renewed-first'}));
  await oldRequest;
  assert.equal(api.getSession().user.id,'second');
});
