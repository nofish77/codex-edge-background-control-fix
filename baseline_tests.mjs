import test from 'node:test';
import assert from 'node:assert/strict';
const {InstalledCdp}=await import(new URL(process.env.EDGE_CDP_FIXTURE??'./.local/cdp-fixture.mjs',import.meta.url));

function fixture({modal=false,denyAttach=false}={}) {
  const trace=[];
  const listeners=new Map();
  const api={
    addEventListener(name,fn){listeners.set(name,fn);},
    async attach(tabId,policy){
      trace.push(['attach',tabId,policy]);
      if(denyAttach)throw new Error('attachment rejected');
    },
    async executeCdp(request){
      trace.push([request.method]);
      if(modal&&request.method==='Emulation.setFocusEmulationEnabled')
        throw new Error('Timed out after 10000ms waiting for CDP command Emulation.setFocusEmulationEnabled.');
      return {};
    }
  };
  const span={withSpan(_name,_attrs,fn){return fn();},currentCommandAttrs(){return {};}};
  const cdp=new InstalledCdp(api,'windows',span,async()=>{trace.push(['readNetworkPolicy']);return {testPolicy:true};});
  return {cdp,trace,listeners};
}

test('normal attachment reads network policy and initializes focus before a normal command',async()=>{
  const {cdp,trace}=fixture();
  await cdp.callTarget({tabId:42},'Page.getFrameTree',{},{});
  assert.deepEqual(trace.slice(0,3).map(x=>x[0]),['readNetworkPolicy','attach','Emulation.setFocusEmulationEnabled']);
  assert.ok(trace.some(x=>x[0]==='Page.enable'));
  assert.equal(trace.at(-1)[0],'Page.getFrameTree');
});

test('a modal during reattachment prevents the actual dialog-close command from being dispatched',async()=>{
  const {cdp,trace}=fixture({modal:true});
  await assert.rejects(cdp.callTarget({tabId:42},'Page.handleJavaScriptDialog',{accept:false},{}),error=>{
    assert.match(error.message,/Emulation.setFocusEmulationEnabled/);
    return true;
  });
  assert.deepEqual(trace.map(x=>x[0]),['readNetworkPolicy','attach','Emulation.setFocusEmulationEnabled']);
  assert.equal(trace.some(x=>x[0]==='Page.handleJavaScriptDialog'),false);
});

test('an attachment rejection is propagated and does not dispatch page commands',async()=>{
  const {cdp,trace}=fixture({denyAttach:true});
  await assert.rejects(cdp.callTarget({tabId:42},'Page.handleJavaScriptDialog',{accept:false},{}),/attachment rejected/);
  assert.deepEqual(trace.map(x=>x[0]),['readNetworkPolicy','attach']);
});

test('a known modal blocks unrelated renderer commands before dispatch',async()=>{
  const {cdp,trace}=fixture();
  cdp.jsDialogsByTabId.set(42,{id:'old-dialog',type:'confirm',target:{tabId:42}});
  await assert.rejects(cdp.callTarget({tabId:42},'Runtime.evaluate',{expression:'1'},{}),/JavaScript dialog is active/);
  assert.deepEqual(trace,[]);
});
