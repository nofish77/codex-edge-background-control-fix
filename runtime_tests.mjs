import test from 'node:test';
import assert from 'node:assert/strict';
import {InstalledCdp,handleInstalledDialog} from './.local/cdp-fixture.mjs';

function setup(){
 const trace=[],listeners=new Map();let attached=false,modal=false,cdp;
 const emit=(method,params={})=>listeners.get('onCDPEvent')?.({method,params,source:{tabId:42}});
 const api={
  addEventListener(n,fn){listeners.set(n,fn)},
  async attach(){attached=true;trace.push({method:'attach'})},
  async executeCdp(request){
   trace.push(request);await new Promise(r=>setImmediate(r));
   if(!attached)throw 'Debugger unattached';
   if(request.method==='Emulation.setFocusEmulationEnabled'&&modal)throw 'Timed out waiting for focus';
   if(request.method.startsWith('Input.')||request.method==='Runtime.evaluate'||request.method==='Runtime.callFunctionOn'){
    modal=true;emit('Page.javascriptDialogOpening',{type:'confirm',message:'synthetic modal',url:'https://www.selenium.dev/selenium/web/alerts.html'});
    if(!request.preserveDebuggerOnTimeout)attached=false;
    throw 'Timed out waiting for input command';
   }
   if(request.method==='Page.handleJavaScriptDialog'){
    assert.ok(modal);modal=false;emit('Page.javascriptDialogClosed',{result:request.commandParams.accept});
   }
   return {};
  }
 };
 const span={withSpan(_n,_a,fn){return fn()},currentCommandAttrs(){return {}}};
 cdp=new InstalledCdp(api,'win32',span,async()=>({approvedTarget:true}));
 return {cdp,trace};
}

for(const method of ['Input.dispatchMouseEvent','Input.dispatchKeyEvent','Input.insertText','Runtime.evaluate','Runtime.callFunctionOn']){
 test(`${method}: a modal-blocked input timeout retains the debugger and supports explicit cancellation`,async()=>{
  const {cdp,trace}=setup();
  await assert.rejects(cdp.callTarget({tabId:42},method,{}),e=>String(e).includes('Timed out waiting for input'));
  const dialog=cdp.getJsDialog(42);assert.equal(dialog.type,'confirm');
  const input=trace.find(x=>x.method===method);assert.equal(input.preserveDebuggerOnTimeout,true);
  await handleInstalledDialog({tab_id:'42',dialog_id:dialog.id,action:'dismiss'},{cdp});
  assert.equal(trace.filter(x=>x.method==='attach').length,1,'no reconnect while dialog is active');
  assert.equal(trace.filter(x=>x.method==='Emulation.setFocusEmulationEnabled').length,1,'no focus initialization during modal');
  assert.equal(trace.find(x=>x.method==='Page.handleJavaScriptDialog').commandParams.accept,false);
  assert.equal(cdp.getJsDialog(42),undefined);
  await cdp.callTarget({tabId:42},'Page.getFrameTree',{});
 });
}

test('ordinary CDP calls retain their original timeout policy',async()=>{
 const {cdp,trace}=setup();
 await cdp.callTarget({tabId:42},'Page.getFrameTree',{});
 assert.equal(trace.findLast(x=>x.method==='Page.getFrameTree').preserveDebuggerOnTimeout,undefined);
});

test('explicit caller preservation is still honored for another method',async()=>{
 const {cdp,trace}=setup();
 await cdp.callTarget({tabId:42},'Page.getFrameTree',{},{preserveDebuggerOnTimeout:true});
 assert.equal(trace.findLast(x=>x.method==='Page.getFrameTree').preserveDebuggerOnTimeout,true);
});
