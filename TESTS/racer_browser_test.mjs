import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const [port,debug]=process.argv.slice(2),base=`http://127.0.0.1:${port}`;
const page=await(await fetch(`http://127.0.0.1:${debug}/json/new?about:blank`,{method:'PUT'})).json();
const ws=new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let seq=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const [ok,bad]=pending.get(m.id);pending.delete(m.id);m.error?bad(m.error):ok(m.result);}};
function call(method,params={}){return new Promise((ok,bad)=>{const id=++seq;pending.set(id,[ok,bad]);ws.send(JSON.stringify({id,method,params}));});}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const keys=async()=> (await(await fetch(base+'/status')).json()).keys;
const key=async(type,key,code,keyCode)=>call('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode:keyCode});
try {
    await call('Page.enable');await sleep(500);
    const navigation=await call('Page.navigate',{url:base});assert.equal(navigation.errorText,undefined);
    let title;
    for(let i=0;i<50;++i){await sleep(100);title=await call('Runtime.evaluate',{expression:'document.title',returnByValue:true});if(title.result.value.includes('Mega Coast'))break;}
    assert.match(title.result.value,/Mega Coast/);await sleep(700);
    await key('keyDown','Enter','Enter',13);await sleep(100);assert.equal((await keys())&16,16);
    await key('keyUp','Enter','Enter',13);await sleep(150);
    await key('keyDown','ArrowUp','ArrowUp',38);await key('keyDown','ArrowLeft','ArrowLeft',37);
    await sleep(150);assert.equal(await keys(),5);
    await key('keyUp','ArrowLeft','ArrowLeft',37);await sleep(150);assert.equal(await keys(),4);
    await call('Runtime.evaluate',{expression:"window.dispatchEvent(new Event('blur'))"});await sleep(150);assert.equal(await keys(),0);
    const screenshot=await call('Page.captureScreenshot');await writeFile('/tmp/racer_controller.png',Buffer.from(screenshot.data,'base64'));
    const bad=await fetch(base+'/controls',{method:'POST',headers:{Origin:'https://example.invalid'},body:'4'});assert.equal(bad.status,403);
    assert.equal(await keys(),0);
} finally {await Promise.race([call('Browser.close'),sleep(1000)]);ws.close();}
