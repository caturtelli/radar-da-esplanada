from pathlib import Path
import shutil
import subprocess
import json
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from history_bridge import BRIDGE

def test_cloud_history_echo_preserves_forward_stack():
    node=shutil.which('node')
    if not node:pytest.skip('Node is only needed for the isolated JavaScript bridge test')
    source=BRIDGE.removeprefix('<script>').removesuffix('</script>')
    program=r'''
const vm=require('node:vm'), assert=require('node:assert/strict');
const states=['https://example.test/?orgao=fazenda','https://example.test/?pessoa=rafael-fonteles'];
let index=1, events=[], timers=[];
const host={location:new URL(states[index]),setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},
 addEventListener(type,fn){events.push(fn)},removeEventListener(type,fn){events=events.filter(f=>f!==fn)}};
host.history={state:{},pushState(state,unused,url){states.splice(++index);states[index]=new URL(url,host.location.href).href;host.location=new URL(states[index]);},
 replaceState(state,unused,url){states[index]=new URL(url,host.location.href).href;host.location=new URL(states[index]);}};
const original=host.history.pushState;
const app={parent:host,location:new URL(states[index]),PopStateEvent:class{constructor(type,props){this.type=type;this.state=props.state;}},
 history:{state:{},replaceState(state,unused,url){app.location=new URL(url)}},
 dispatchEvent(){host.history.pushState({},'',host.location.href)}};
const context={window:{parent:app},URL,clearTimeout(){}};
vm.runInNewContext(SOURCE,context);
vm.runInNewContext(SOURCE,context);
assert.equal(events.length,1,'reinstall removes the previous listener');
index=0;host.location=new URL(states[index]);events[0]();while(timers.length)timers.shift()();
assert.equal(app.location.search,'?orgao=fazenda');
assert.equal(index,0,'the Cloud echo must not push a duplicate history entry');
assert.equal(states.length,2,'Forward target is preserved');
index=1;host.location=new URL(states[index]);events[0]();while(timers.length)timers.shift()();
assert.equal(app.location.search,'?pessoa=rafael-fonteles');
assert.equal(index,1);assert.equal(states.length,2);
host.history.pushState({},'','?tela=noticias');
assert.equal(index,2,'genuine user navigation still creates an entry');
host.__radarSameOriginHistoryBridge.dispose();
assert.equal(host.history.pushState,original,'dispose restores the original history method');
'''.replace('SOURCE',json.dumps(source))
    result=subprocess.run([node,'-e',program],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
