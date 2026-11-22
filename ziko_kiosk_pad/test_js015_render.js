const fs=require('fs'),vm=require('vm'),assert=require('assert');
const script=fs.readFileSync(0,'utf8');
const C=function(){};
C.prototype._render=function(){};C.prototype._click=function(){};C.prototype.connectedCallback=function(){};
const context={window:{innerHeight:768,customElements:{get:function(n){return n==='ziko-kiosk-lights'?C:null;}},setInterval:function(){throw Error('unexpected retry');},setTimeout:function(){return 0;}},document:{createElement:function(){return {setAttribute:function(){}}}},console:console};
vm.runInNewContext(script,context,{filename:'skin.js',timeout:4000});
assert(C.prototype.__zikoPad015);
const app=Object.create(C.prototype);app._container={innerHTML:''};app.shadowRoot={appendChild:function(){}};
app._hass={};app._online=function(){return true;};app._stats=function(){return {on:1,available:2,all:2};};
app._level=function(){return 75;};app._st=function(){return {state:'off',attributes:{}};};
app._valid=function(){return true;};app._corridorSeconds=function(){return 60;};
app._corridorTimerActive=function(){return false;};app._kelvin=2700;app._color='#00e5d4';app._lightsBusy=false;
function check(count,names){app._render();const h=app._container.innerHTML;assert.equal((h.match(/data-pad-card=/g)||[]).length,count);names.forEach(function(n){assert(h.includes('data-pad-card="'+n+'"'),n+' missing');});assert(h.includes('<main class="lkp-area">'));assert(h.includes('style="height:768px!important;min-height:768px!important"'));}
check(6,['nagyszoba','agy','govee','nappali','konyha','furdo']);
app._padPage=1;check(4,['eloszoba','erkely','kozos','kozlekedo']);
app._padView='scenes';check(0,[]);
console.log('JS015_RENDER_SMOKE PASS: six rooms, four secondary controls, scenes');
