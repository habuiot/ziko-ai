/* ZIKO Kiosk Pad v0.3.15 • isolated visual replacement for the iPad 2 lighting page.
   Reuses the original copied Miix Kiosk's validated HA services, whitelist,
   safety rules, DreamView restrictions and physical lock separation.
   ES5 only: iOS 9 Safari. DO NOT load in the source Miix Kiosk. */
(function(){
  'use strict';
  function install(){
  var C=window.customElements && window.customElements.get('ziko-kiosk-lights');
  if(!C)return false;
  if(C.prototype.__zikoPad015)return true;
  C.prototype.__zikoPad015=true;
  var CSS_URL='/kiosk-pad/assets/pad-lights-015.css';
  var ALL_GROUPS=[
    ['nagyszoba','Nagyszoba','🛋'],['agy','Ágyfények együtt','🛏'],
    ['govee','Govee TV','▣'],['nappali','Nappali','⌂'],
    ['konyha','Konyha','♜'],['furdo','Fürdőszoba','♨'],
    ['eloszoba','Előszoba','▣'],['erkely','Erkély','☘'],
    ['kozos','Nappali + Konyha','✦'],['kozlekedo','Közlekedő','◈']
  ];
  var SCENES=[
    ['esti','☾ Esti','Meleg 35%'],['mozi','▣ Mozi','Meleg 15%'],
    ['relax','✿ Relax','Türkiz 35%'],['takaritas','♧ Takarítás','Fehér 100%'],
    ['ejszaka','☾ Éjszaka','Meleg 10%'],['szines','◉ Színes','Türkiz 70%']
  ];
  var COLORS=[['#ffbf8a','Melegfehér','warm'],['#ff4658','Piros','red'],['#ffb12a','Narancs'],['#ffe85a','Sárga'],['#44d76e','Zöld'],['#00e5d4','Türkiz','teal'],['#6562e8','Kék'],['#db40d7','Lila']];
  function safeNum(v,lo,hi,fallback){var n=Number(v);return isFinite(n)?Math.min(hi,Math.max(lo,Math.round(n))):fallback;}
  function txt(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function lgroup(id){for(var i=0;i<ALL_GROUPS.length;i++){if(ALL_GROUPS[i][0]===id)return ALL_GROUPS[i];}return null;}
  function powerSymbol(){return '⏻';}
  function b(text,act,extra,cls,disabled){return '<button type="button" '+(act?'data-act="'+act+'" ':'')+(extra||'')+' class="'+(cls||'')+'" '+(disabled?'disabled':'')+'>'+text+'</button>';}
  function slot(n,v){return '<label class="lkp-label">'+n+'</label>'+v;}
  function validGroup(self,id){return self._stats(id).available>0 && self._online() && !self._lightsBusy;}
  function level(self,id){return safeNum(self._level(id),1,100,100);}
  function range(self,id){var n=level(self,id);return '<input type="range" class="lkp-slider" data-lk-range="'+id+'" min="1" max="100" value="'+n+'" aria-label="'+txt((lgroup(id)||['','Összes'])[1])+' fényerő" '+(!validGroup(self,id)?'disabled':'')+'>'}
  function presets(self,id){var disable=!validGroup(self,id);return '<div class="lkp-card-actions">'+
    b('Meleg','', 'data-padkelvin="2700" data-group="'+id+'"','warm',disable)+
    b('Semleges','', 'data-padkelvin="4000" data-group="'+id+'"','',disable)+
    b('Hideg','', 'data-padkelvin="6500" data-group="'+id+'"','',disable)+
    b('Szín','lk-editor-open','data-group="'+id+'" data-mode="color"','color',disable)+'</div>';
  }
  function roomCard(self,item){
    var id=item[0],s=self._stats(id),on=s.on>0,n=level(self,id),enabled=validGroup(self,id);
    var status=enabled?(s.on+' aktív / '+s.available+' elérhető'):'Nem elérhető';
    var h='<article class="lkp-card" data-pad-card="'+id+'" aria-label="'+txt(item[1])+'">'+
      '<div class="lkp-card-row"><div class="lkp-card-title"><strong>'+txt(item[2]+' '+item[1])+'</strong><small>'+status+'</small></div>'+
      b(powerSymbol(),'lk-power','data-group="'+id+'" aria-label="'+txt(item[1])+' '+(on?'kikapcsolás':'bekapcsolás')+'"','lkp-power'+(on?' on':''),!enabled)+'</div>'+
      '<div class="lkp-card-dim"><label>Fényerő</label>'+range(self,id)+'<strong data-lk-label="'+id+'">'+n+'%</strong></div>'+presets(self,id);
    if(id==='govee'){
      var dream=self._st('switch.nagyszoba_tv_hattervilagitas_dreamview');
      var active=dream && dream.state==='on';
      h+='<div class="lkp-dream-row">'+
        b('DreamView '+(active?'BE':'KI'),'lk-dream','aria-label="Govee DreamView váltása"','',!dream||!self._valid('switch.nagyszoba_tv_hattervilagitas_dreamview'))+
        (active?' · Színzár aktív':' · Fix szín engedélyezve')+'</div>';
    }
    return h+'</article>';
  }
  function corridorCard(self){
    var s=self._stats('kozlekedo'),online=validGroup(self,'kozlekedo'),on=s.on>0;
    var sync=self._st('input_boolean.ziko_kozlekedo_nappali_konyha_kovetes');
    var motion=self._st('input_boolean.ziko_kozlekedo_pir_automatikus_feny_engedelyezve');
    function tog(label,act,entity){var on=entity&&entity.state==='on';return '<div class="lkp-corridor-toggle"><span>'+label+'</span>'+b(on?'BE':'KI',act,'aria-checked="'+(on?'true':'false')+'" role="switch"',''+(on?'on':''),!entity||!self._online())+'</div>';}
    var secs=self._corridorSeconds();
    return '<article class="lkp-card lkp-corridor" data-pad-card="kozlekedo">'+
       '<div class="lkp-card-row"><div class="lkp-card-title"><strong>◈ Közlekedő</strong><small>'+ (online?(on?'Bekapcsolva':'Kikapcsolva'):'Nem elérhető')+'</small></div>'+
       b(powerSymbol(),'lk-power','data-group="kozlekedo" aria-label="Közlekedő kapcsoló"','lkp-power'+(on?' on':''),!online)+'</div>'+
       '<div class="lkp-card-actions">'+tog('Nappali + Konyha követés','lk-corridor-sync',sync)+tog('Mozgásérzékelő','lk-corridor-motion',motion)+
       '<div class="lkp-delay"><label>Időzítő</label><input type="range" class="lkp-slider" data-lk-corridor-range min="10" max="300" step="5" value="'+secs+'" '+(!online?'disabled':'')+'><span data-lk-corridor-seconds>'+secs+' mp</span></div>'+
       (self._corridorTimerActive()?'<div class="lkp-timer">Mozgásos visszaszámlálás: <strong data-lk-countdown>'+self._corridorTime()+'</strong></div>'+b('Időzítő megállítása','lk-corridor-stop','','lkp-stop',false):'<div class="lkp-timer">Kézi tartás / időzítő készenlét</div>')+'</div></article>';
  }
  function modal(self){
    var e=self._roomEditor;if(!e)return '';
    var info=lgroup(e.id)||['','Lámpacsoport'];
    var white=e.mode!=='color';
    return '<div class="lkp-modal-mask"><section class="lkp-modal" role="dialog" aria-modal="true" aria-label="Egyedi szín">'+
      '<h2>'+txt(info[1])+' – Egyedi '+(white?'fehér':'szín')+'</h2><p>Csak a kiválasztott helyiség lámpáira vonatkozik.</p>'+
      (white?'<div class="lkp-modal-row"><label>Színhőmérséklet: <strong data-lk-editor-kelvin>'+e.kelvin+' K</strong></label><input type="range" min="2200" max="6500" step="100" value="'+e.kelvin+'" data-lk-editor-kelvin-input></div>':
      '<div class="lkp-modal-row"><label>RGB-szín <strong data-lk-editor-colorlabel>'+txt(e.color.toUpperCase())+'</strong></label><input type="color" data-lk-editor-color value="'+txt(e.color)+'"></div>')+
      (e.id==='govee'&&!self._goveeFixedColor()?'<p>DreamView/effekt aktív: a kézi színvezérlés le van tiltva.</p>':'')+
      '<div class="lkp-modal-quick"><span>Gyorsszínek: </span>'+b('Meleg','lk-preset','data-group="'+e.id+'" data-color="warm"','',false)+b('Türkiz','lk-preset','data-group="'+e.id+'" data-color="teal"','',false)+b('Piros','lk-preset','data-group="'+e.id+'" data-color="red"','',false)+'</div>'+
      '<div class="lkp-modal-actions">'+b('Mégse','lk-editor-close','','',false)+b('Alkalmaz',white?'lk-editor-apply-white':'lk-editor-apply-color','','lkp-apply',e.id==='govee'&&!self._goveeFixedColor())+'</div></section></div>';
  }
  function sceneView(self){var html='<div class="lkp-scene-view">';for(var i=0;i<SCENES.length;i++){
    var a=SCENES[i];html+=b(txt(a[1])+'<small>'+txt(a[2])+'</small>','','data-padscene="'+a[0]+'"','',!self._online());
  }return html+'</div>';}
  var oldRender=C.prototype._render;
  C.prototype._render=function(){
    if(!this._container||!this._hass||this._lightsBusy)return;
    if(!this.__padStyleAttached){
      var link=document.createElement('link');link.setAttribute('rel','stylesheet');link.setAttribute('href',CSS_URL);this.shadowRoot.appendChild(link);this.__padStyleAttached=true;
    }
    var view=this._padView||'all',page=this._padPage||0;
    var total=this._stats('all'),lvl=level(this,'all'),online=this._online(),on=total.on>0;
    var tabs=[['all','Összes'],['rooms','Szobák'],['groups','Csoportok'],['scenes','Jelenetek']],nav='';
    for(var i=0;i<tabs.length;i++)nav+=b(tabs[i][1],'','data-padview="'+tabs[i][0]+'"',''+(view===tabs[i][0]?'current':''),false);
    var white='';for(var k=0;k<3;k++){var kv=[2700,4000,6500][k];white+=b(['Meleg','Semleges','Hideg'][k],'','data-padkelvin="'+kv+'" data-group="all"','',!online);}
    var colors='';for(var j=0;j<COLORS.length;j++){var col=COLORS[j];colors+=b('&nbsp;',col[2]?'lk-preset':'', (col[2]?'data-color="'+col[2]+'" data-group="all" ':'data-padcolor="'+col[0]+'" ')+'title="'+col[1]+'" style="background:'+col[0]+'"',''+(this._color===col[0]?'chosen':''),!online);}
    var sceneb='';for(var q=0;q<SCENES.length;q++){sceneb+=b(txt(SCENES[q][1]),'','data-padscene="'+SCENES[q][0]+'"','',!online);}
    var isPage2=view==='groups'||(view==='all'&&page===1);
    var title=view==='scenes'?'Jelenetek':isPage2?'További helyiségek':'Helyiségek és fénycsoportok';
    var cards='';
    if(view==='scenes')cards=sceneView(this);
    else if(isPage2)cards='<div class="lkp-cards is-four">'+roomCard(this,ALL_GROUPS[6])+roomCard(this,ALL_GROUPS[7])+roomCard(this,ALL_GROUPS[8])+corridorCard(this)+'</div>';
    else {cards='<div class="lkp-cards">';for(var x=0;x<6;x++)cards+=roomCard(this,ALL_GROUPS[x]);cards+='</div>';}
    var pageBtns=view==='all'?'<div class="lkp-pager">'+b('❮','','data-padpage="0"','',page===0)+b('❯','','data-padpage="1"','',page===1)+'<span>'+(page+1)+'/2</span></div>':'';
    /* Real Safari 9 iPad diagnostic: .lkp-area was 0px even with 6 DOM cards.
       Percent root height inherited an auto-height shadow host. Supply an
       explicit device viewport pixel height so the positioned card area has
       a definite containing block. Preserve original Miix and controls. */
    var viewportHeight=Number(window.innerHeight||(document.documentElement&&document.documentElement.clientHeight)||768);
    if(!isFinite(viewportHeight)||viewportHeight<320)viewportHeight=768;
    viewportHeight=Math.round(Math.min(1800,viewportHeight));
    this._container.innerHTML='<div class="kiosk lk-pad" style="height:'+viewportHeight+'px!important;min-height:'+viewportHeight+'px!important">'+
      '<header class="lkp-header"><div class="lkp-brand"><b>⌂</b> Ziko Kiosk</div><div id="main-clock" class="lkp-clock">'+new Date().toLocaleTimeString('hu-HU')+'</div><nav class="lkp-nav">'+
      b('⌂','kiosk-section','data-section="thermostat" aria-label="Termosztát"','',false)+
      b('◐','kiosk-section','data-section="lights" aria-label="Világítások"','',false)+
      b('⚙','fullscreen','aria-label="Teljes képernyő"','',false)+
      b('⌂ HA-Ziko','fullscreen','aria-label="Házikó kapcsolat"','lkp-home',false)+'</nav></header>'+
      '<div class="lkp-heading"><div class="lkp-title"><strong>☀ Világítások</strong><span>Lámpák · helyiségek · csoportok · jelenetek</span></div><div class="lkp-tabs">'+nav+'</div></div>'+
      '<section class="lkp-master"><div class="lkp-master-top"><div><span class="lkp-power-mark">'+powerSymbol()+'</span><strong>Összes lámpa</strong><small>Aktív '+total.on+'/'+total.available+'</small></div>'+
      b((on?'MINDEN KI':'MINDEN BE'),'lk-power','data-group="all"','lkp-alloff',!online)+'</div>'+
      '<div class="lkp-master-lines"><div class="lkp-master-left">'+
      '<div class="lkp-row">'+slot('☼ Fényerő',range(this,'all')+'<span class="lkp-level" data-lk-label="all">'+lvl+'%</span>')+'</div>'+
      '<div class="lkp-row">'+slot('☀ Fehér','<div class="lkp-temp">'+white+'</div>')+'</div>'+
      '<div class="lkp-row">'+slot('◉ Színek','<div class="lkp-colors">'+colors+'</div>')+'</div></div>'+
      '<div class="lkp-master-right"><div class="lkp-prompt"><strong>Egyedi fehér</strong><span data-lk-kvalue>'+this._kelvin+' K</span></div>'+
      '<div class="lkp-prompt"><input type="range" class="lkp-slider" data-lk-kelvin min="2200" max="6500" step="100" value="'+this._kelvin+'"></div>'+
      '<div class="lkp-prompt">'+b('Fehér','lk-white','','lkp-apply',!online)+'<input type="color" data-lk-custom value="'+txt(this._color)+'">'+b('Szín','lk-color','','lkp-apply',!online)+'</div></div></div></section>'+
      '<div class="lkp-scenes"><b>✦ Gyors jelenetek</b>'+sceneb+'</div>'+
      '<div class="lkp-section"><strong>'+txt(title)+'</strong>'+pageBtns+'</div><main class="lkp-area">'+cards+'</main>'+
      (this._notice?'<div class="lkp-status" role="status">'+txt(this._notice)+'</div>':'')+modal(this)+'</div>';
    /* Device-side geometry proof: one sanitized diagnostic event per view,
       independent of WebKit remote inspector, no sensor or credential values. */
    var self=this,which=view==='all'?('p'+page):view;
    if(!this.__pad015Seen)this.__pad015Seen={};
    if(!this.__pad015Seen[which]){
      this.__pad015Seen[which]=true;
      window.setTimeout(function(){
        var area=self._container&&self._container.querySelector('.lkp-area');
        var list=area&&area.querySelector('.lkp-cards');
        var tile=list&&list.querySelector('.lkp-card');
        if(!area||!window.__zkPadDiag)return;
        var pad=self._container.querySelector('.lk-pad');
        var rootH=pad?Math.round(pad.getBoundingClientRect().height):0;
        var ah=Math.round(area.getBoundingClientRect().height);
        var th=tile?Math.round(tile.getBoundingClientRect().height):0;
        var count=list?list.children.length:0;
        window.__zkPadDiag('probe','lights-015-'+which,'viewport:'+Math.round(window.innerHeight||0)+' root:'+rootH+' area:'+ah+' cards:'+count+' tile:'+th,0);
      },1200);
    }

  };
  var oldClick=C.prototype._click;
  C.prototype._click=function(e){
    var t=e.target && e.target.closest?e.target.closest('button'):null;
    if(t && !t.disabled){
      if(t.hasAttribute('data-padview')){this._padView=t.getAttribute('data-padview');this._padPage=0;this._render();return;}
      if(t.hasAttribute('data-padpage')){this._padView='all';this._padPage=Number(t.getAttribute('data-padpage'))===1?1:0;this._render();return;}
      if(t.hasAttribute('data-padcolor')){this._color=t.getAttribute('data-padcolor');this._render();return;}
      if(t.hasAttribute('data-padkelvin')){this._white(t.getAttribute('data-group')||'all',Number(t.getAttribute('data-padkelvin')));return;}
      if(t.hasAttribute('data-padscene')){this._applyPadScene(t.getAttribute('data-padscene'));return;}
    }
    return oldClick.call(this,e);
  };
  C.prototype._applyPadScene=function(id){
    var self=this, modes={
      esti:{level:35,color:'warm'}, mozi:{level:15,color:'warm'},
      relax:{level:35,color:'teal'}, takaritas:{level:100,color:'white'},
      ejszaka:{level:10,color:'warm'}, szines:{level:70,color:'teal'}
    },p=modes[id];
    if(!p||!this._online()||this._lightsBusy)return;
    this._levels.all=p.level;
    var action=p.color==='white'?this._white('all',5000):p.color==='warm'?this._white('all',2700):this._colorAction('all','#00e5d4');
    if(action && typeof action.then==='function')action.then(function(){self._levels.all=p.level;self._brightness('all');});
  };
  var oldConnected=C.prototype.connectedCallback;
  C.prototype.connectedCallback=function(){
    if(oldConnected)oldConnected.call(this);
    if(this.__padSwipeReady)return;
    this.__padSwipeReady=true;
    var self=this,start=null;
    this.shadowRoot.addEventListener('touchstart',function(e){
      var a=e.target.closest?e.target.closest('.lkp-area'):null;
      if(!a||e.target.closest('input,button')){start=null;return;}
      start={x:e.touches[0].clientX,y:e.touches[0].clientY};
    },false);
    this.shadowRoot.addEventListener('touchend',function(e){
      if(!start||self._padView&&self._padView!=='all'){start=null;return;}
      var dx=e.changedTouches[0].clientX-start.x,dy=e.changedTouches[0].clientY-start.y;
      start=null;
      if(Math.abs(dx)<90||Math.abs(dx)<Math.abs(dy)*1.8)return;
      self._padView='all';self._padPage=dx<0?1:0;self._render();
    },false);
  };
  window.__zikoPadLights015=true;
  return true;
  }
  if(!install()){
    var attempt=0,wait=window.setInterval(function(){
      attempt++;if(install()||attempt>=60)window.clearInterval(wait);
    },250);
  }
})();
