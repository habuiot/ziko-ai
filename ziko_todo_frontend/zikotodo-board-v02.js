/* ZikoTodo v0.2 - independent Home Assistant UI, no extra account. */
(function () {
  "use strict";
  const TAG = "ziko-todo-board-v2";
  if (customElements.get(TAG)) return;
  const LISTS = [
    { key: "ai", id: "todo.zikotodo_ai_feladatok", name: "AI-feladatok", short: "AI", icon: "robot", color: "cyan" },
    { key: "human", id: "todo.zikotodo_emberi_feladatok", name: "Saját feladataim", short: "Én", icon: "account", color: "lime" },
    { key: "team", id: "todo.zikotodo_csapatfeladatok", name: "Csapatfeladatok", short: "Csapat", icon: "account-group", color: "violet" }
  ];
  const FLOW = ["Beérkezett", "Folyamatban", "Ellenőrzés", "Blokkolt", "Kész"];
  const escapeHtml = value => String(value == null ? "" : value).replace(/[&<>"']/g, chr => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[chr]);
  const dateText = value => value ? new Date(String(value).slice(0,10) + "T12:00:00").toLocaleDateString("hu-HU", { month:"short", day:"numeric" }) : "";
  function info(text, completed) {
    const raw = String(text || "");
    const result = { project:"Általános", owner:"", priority:"Normál", stage:completed ? "Kész" : "Beérkezett", note:raw };
    if (raw.startsWith("ZIKO-TODO/1\n")) {
      const [meta, ...parts] = raw.slice(12).split("\n---\n");
      const m = {};
      for (const line of meta.split("\n")) {
        const p = line.indexOf(": ");
        if (p > 0) m[line.slice(0,p)] = line.slice(p+2);
      }
      result.project = m.Projekt || result.project;
      result.owner = m["Felelős"] || "";
      result.priority = m["Prioritás"] || "Normál";
      result.stage = completed ? "Kész" : m.Folyamat==="Kész" ? "Ellenőrzés" : m.Folyamat || "Beérkezett";
      result.note = parts.join("\n---\n");
    } else {
      const p = raw.match(/Projekt:\s*([^|\n]+)/i);
      if (p) result.project = p[1].trim();
      result.note = raw.replace(/^Projekt:\s*[^|\n]+\s*\|\s*/i, "").trim();
      const state = raw.match(/(?:Állapot|Folyamat):\s*([^|;.\n]+)/i);
      if (state && FLOW.includes(state[1].trim())) result.stage = state[1].trim();
    }
    return result;
  }
  function description(meta) {
    return "ZIKO-TODO/1\nProjekt: " + (meta.project || "Általános") +
      "\nFelelős: " + (meta.owner || "") +
      "\nPrioritás: " + (meta.priority || "Normál") +
      "\nFolyamat: " + (meta.stage || "Beérkezett") +
      "\n---\n" + (meta.note || "");
  }
  const CSS = [
    ":host{display:block;font-family:Inter,Roboto,'Segoe UI',sans-serif;--zt:#ecf9ff;--zm:#9fb4c8;--zb:#0b1420;--zc:#67e7fa;color:var(--zt);width:100%;}",
    "*{box-sizing:border-box;}button,input,select,textarea{font:inherit;}button{cursor:pointer;}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #7aeaff;outline-offset:2px;}",
    ".app{background:radial-gradient(ellipse at 8% 0%,#123146 0%,transparent 39%),radial-gradient(ellipse at 100% 85%,#1c1937 0%,transparent 37%),#0b121c;border:1px solid rgba(122,216,240,.2);border-radius:22px;padding:clamp(13px,2.8vw,29px);min-height:440px;overflow:hidden;box-shadow:0 18px 55px #0003;}",
    ".header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:20px}.eyebrow{letter-spacing:2.8px;font-size:10px;color:#78c9d7;font-weight:800}.brand{font-size:clamp(27px,4vw,44px);margin:2px 0 4px;line-height:1.1;letter-spacing:-1px;font-weight:900}.brand b{color:#7be8f6}.sub{font-size:12px;color:var(--zm)}.live{font-size:11px;border:1px solid #355061;background:#142635;border-radius:999px;padding:9px 12px;color:#91f1e7}.live span{display:inline-block;width:6px;height:6px;border-radius:50%;background:#62eacb;margin-right:7px}",
    ".kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:17px}.kpi{background:#122331c9;border:1px solid #254256;border-radius:14px;padding:13px 14px}.kpi .num{font-weight:850;font-size:clamp(23px,3.4vw,31px);line-height:1.1;margin:5px 0}.kpi .label{color:#9cb7cb;font-size:11px}.kpi.cyan{border-left:3px solid #59ddf4}.kpi.lime{border-left:3px solid #b7e780}.kpi.violet{border-left:3px solid #b29bfb}.kpi.gold{border-left:3px solid #f8c678}",
    ".nav{display:flex;gap:7px;overflow:auto;padding-bottom:8px;margin-bottom:14px;scrollbar-width:thin}.nav button,.btn,.chip{border-radius:10px;border:1px solid #30485e;background:#16283a;color:#c5d8e6;padding:9px 13px;white-space:nowrap;font-weight:650;font-size:12px}.nav button[aria-current='page']{color:#09141f;background:#81e7f8;border-color:#81e7f8}.nav button:hover,.btn:hover{border-color:#77deef}.tools{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:12px}.tools .search{flex:1;min-width:185px;max-width:480px}.field{background:#101f30;color:#e8f6fc;border:1px solid #30465c;border-radius:10px;padding:11px 12px;width:100%;outline:none}.field::placeholder{color:#849daf}.field:focus{border-color:#69dfee;box-shadow:0 0 0 2px #4de0f42a}",
    ".compose{border:1px solid #2b5362;border-radius:15px;background:linear-gradient(115deg,#142739e8,#111d2fe8);padding:14px;margin-bottom:17px}.compose .comp-title{font-size:11px;color:#7de9fa;font-weight:800;letter-spacing:1.1px;margin-bottom:11px}.compose-grid{display:grid;grid-template-columns:2.1fr 1fr 1fr auto;gap:9px}.compose-extra{display:grid;grid-template-columns:1.2fr 1fr 1fr 2fr;gap:8px;margin-top:9px}.primary{color:#08212d;background:#7be6f5;border:1px solid #7be6f5;font-weight:850;padding:10px 16px;border-radius:10px}.primary:hover{background:#b0f6ff}.secondary{background:transparent;color:#b3d4e2;border:1px solid #344b5c;border-radius:9px;padding:9px 12px}.hint{font-size:11px;color:#8ba5b9;margin-top:8px;line-height:1.5}",
    ".rows{display:grid;gap:9px}.task{display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:center;background:#122131;border:1px solid #274155;border-radius:13px;padding:13px 12px;transition:border-color .12s}.task:hover{border-color:#489cb0}.task.done{opacity:.67}.task button.check{width:21px;height:21px;border-radius:7px;background:#0f1a28;border:1.5px solid #4c6c82;color:#a8f0da;font-weight:900}.task.done button.check{background:#24745e;border-color:#369b7d}.task-title{font-size:13px;color:#ebf5fa;font-weight:750;line-height:1.35;word-break:break-word}.task.done .task-title{text-decoration:line-through}.meta{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-top:6px}.pill{font-size:10px;border-radius:5px;padding:3px 6px;background:#1a3143;color:#b8cbdb;border:1px solid #29445a}.pill.ai{color:#7ce8fa;background:#123447}.pill.human{color:#d8f3ac;background:#293b2c}.pill.team{color:#dbcaff;background:#302544}.pill.warn{color:#ffd594;background:#423324}.pill.urgent{color:#ffc0af;background:#3e2424}.task-actions{display:flex;align-items:center;gap:5px}.task-actions button{color:#9fd3e1;background:none;border:none;padding:6px;border-radius:6px}.task-actions button:hover{background:#244055}.textnote{font-size:11px;color:#91a6b8;margin-top:5px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:600px}",
    ".section-label{font-size:13px;font-weight:750;margin:16px 0 9px;color:#d7ecf5}.no-items{padding:25px 16px;border:1px dashed #37506a;color:#a4b9c9;text-align:center;border-radius:13px;background:#111e2c}.kanban{display:grid;grid-template-columns:repeat(4,minmax(210px,1fr));gap:10px;overflow:auto;padding-bottom:9px}.lane{background:#0f1d2b;border:1px solid #2c475b;border-radius:13px;padding:9px;min-height:135px}.lane h3{font-size:12px;font-weight:800;margin:5px 6px 11px;color:#dbeef5}.lane .task{display:block;margin-bottom:8px;padding:11px}.lane .task .task-actions{margin-top:9px;justify-content:flex-end}.lane .task>.check{float:right}",
    ".projects{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}.project{padding:18px;border:1px solid #315064;border-radius:14px;text-align:left;color:#e5f4fb;background:linear-gradient(145deg,#142d3f,#152135);min-height:117px}.project strong{display:block;font-size:15px;margin:10px 0 5px}.project small{font-size:11px;color:#9fbad0}.project:hover{border-color:#7ae6f6}.foot{display:flex;justify-content:space-between;align-items:center;gap:10px;border-top:1px solid #294050;margin-top:16px;padding-top:13px;font-size:10px;color:#839eb1;flex-wrap:wrap}.footer-warn{font-size:11px;color:#ffc98f;line-height:1.45}.error{color:#ffc2bc;background:#3d2024;padding:12px;border-radius:9px;margin:12px 0}",
    ".editor{background:#15293b;border:1px solid #52849a;border-radius:14px;padding:16px;margin:14px 0}.editor h3{margin:0 0 12px;font-size:16px}.editor-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.editor label{display:block;color:#b2c8d8;font-size:11px;margin-bottom:3px}.editor label input,.editor label select,.editor label textarea{margin-top:5px}.editor .wide{grid-column:span 3}.editor textarea{height:92px;resize:vertical}.editor-actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}.danger{color:#ffb5b5;border-color:#7a4141}.loading{padding:30px;text-align:center;color:#85b4c7}",
    "@media(max-width:900px){.compose-grid{grid-template-columns:1fr 1fr}.compose-grid .fulltitle{grid-column:span 2}.compose-extra{grid-template-columns:1fr 1fr}.kpis{grid-template-columns:repeat(2,1fr)}.kanban{grid-template-columns:repeat(4,minmax(220px,1fr))}}",
    "@media(max-width:560px){.app{border-radius:12px;padding:13px}.header{gap:9px}.kpi{padding:11px}.compose-grid,.compose-extra{grid-template-columns:1fr}.compose-grid .fulltitle{grid-column:span 1}.editor-grid{grid-template-columns:1fr}.editor .wide{grid-column:span 1}.task{grid-template-columns:23px 1fr auto;padding:10px 8px}.task-actions button{padding:5px}.live{padding:7px 9px}.brand{font-size:30px}.sub{font-size:11px}.kpis{gap:7px}}"
  ].join("") + "\n/* ZIKO Kanban / premium neon skin */\n:host{color-scheme:dark} .app{background:radial-gradient(ellipse at 0 0,#16354a 0,transparent 48%),radial-gradient(ellipse at 100% 0,#2d234f 0,transparent 49%),#090f19;border:1px solid #324e68;border-radius:20px;box-shadow:0 16px 42px #0006,inset 0 1px #ffffff10}\n.header{border-bottom:1px solid #2d4457;padding-bottom:14px;margin-bottom:14px}.eyebrow{display:flex;align-items:center;gap:7px;color:#84ddec}.eyebrow ha-icon{--mdc-icon-size:16px}.brand{letter-spacing:-1.4px;text-shadow:0 0 22px #59dff622}.brand b{background:linear-gradient(90deg,#7df0ff,#bfb0ff);-webkit-background-clip:text;background-clip:text;color:transparent}.live{font-weight:800;letter-spacing:.6px;border-color:#2f766b;color:#8effd2;background:#102923}\n.kpis{gap:8px}.kpi{background:linear-gradient(145deg,#132535,#101e2d);border:1px solid #2c465b;border-radius:11px;padding:11px 13px}.kpi .num{font-size:clamp(24px,3vw,30px);margin:3px 0}.kpi .label{display:flex;align-items:center;gap:6px;font-size:10px;letter-spacing:.2px}.kpi ha-icon{--mdc-icon-size:16px}\n.kpi.cyan .num{color:#80ecff}.kpi.lime .num{color:#d0f3a0}.kpi.violet .num{color:#d4c0ff}.kpi.gold .num{color:#ffe1a4}\n.nav{background:#101d2c;padding:6px;margin:0 0 14px;border:1px solid #263d52;border-radius:12px;gap:4px;scrollbar-width:thin}.nav button{display:flex;align-items:center;gap:6px;border:1px solid transparent;background:transparent;padding:8px 11px;border-radius:8px;min-height:36px}.nav button ha-icon{--mdc-icon-size:18px}.nav button[aria-current='page']{background:#173c51;color:#8eebfc;border-color:#438ba2;box-shadow:inset 0 0 0 1px #27485b}\n.compose{border-color:#305a6d;background:linear-gradient(118deg,#132a3c,#141a2f);padding:12px 13px}.compose .comp-title{color:#9aecff}.primary{background:linear-gradient(105deg,#7ae5f7,#b9adfa);border-color:transparent;color:#092032}.primary:hover{filter:brightness(1.1)}.field{background:#0b1928;border-color:#304a60}.field:focus{border-color:#7deaff}\n.kanban{display:grid;grid-template-columns:repeat(4,minmax(205px,1fr));gap:9px;overflow-x:auto;scrollbar-width:thin;padding-bottom:8px;align-items:stretch}.lane{--lane:#7deaff;min-width:0;background:#0e1a29;border:1px solid #30475c;border-top:3px solid var(--lane);border-radius:13px;padding:9px;min-height:220px;transition:background 140ms,border-color 140ms,box-shadow 140ms}\n.lane-cyan{--lane:#73e9ff}.lane-gold{--lane:#f8cf86}.lane-violet{--lane:#baa8ff}.lane-rose{--lane:#f4a6b8}.lane h3{display:flex;align-items:center;gap:7px;margin:3px 4px 11px;color:var(--lane);font-size:12px;font-weight:800}.lane h3 ha-icon{--mdc-icon-size:18px}.lane-count{margin-left:auto;background:#233545;color:#d6e7f1;border-radius:7px;padding:3px 7px;font-size:11px}\n.lane.drop-target{background:#193747;border-color:#83edff;box-shadow:0 0 0 2px #80eafa55,inset 0 0 30px #40bbd91c}.task.dragging{opacity:.35}.lane .task[draggable]{cursor:grab}.lane .task[draggable]:active{cursor:grabbing}.lane .task{display:block;background:linear-gradient(145deg,#15293a,#131f2d);border:1px solid #2b475c;border-left:2px solid var(--lane);border-radius:9px;padding:10px;margin-bottom:8px;transition:border-color 130ms,transform 130ms}\n.lane .task:hover{border-color:#83d4e9;transform:translateY(-1px)}.lane .task .task-main{margin:8px 0 0}.lane .task .task-title{font-size:12px}.lane .task .meta{gap:4px}.lane .task .task-actions{margin:5px 0 0}.lane .task .check{display:inline-flex;align-items:center;justify-content:center;float:right}\n.empty-lane{border:1px dashed #334e61;border-radius:10px;padding:18px 8px;color:#7495ac;font-size:11px;text-align:center;line-height:1.5}.stage-select{margin-top:8px;font-size:11px;padding:8px 10px;width:100%;border-radius:8px;min-height:36px;color:#bfeef5}\n.task-actions button{font-size:16px}.pill{border-radius:6px;font-size:10px}.pill.ai{color:#84e9ff}.pill.human{color:#d7fca8}.pill.team{color:#e1caff}.pill.urgent{color:#ffb8a9}\n@media(max-width:760px){.kanban{grid-auto-flow:column;grid-auto-columns:minmax(235px,80vw);grid-template-columns:none;scroll-snap-type:x proximity;overscroll-behavior-x:contain}.lane{scroll-snap-align:start}.header{margin-bottom:10px}.kpis{gap:6px}.kpi{padding:9px}.kpi .num{font-size:24px}.nav{margin-bottom:10px}.compose{margin-bottom:11px}}\n@media(prefers-reduced-motion:reduce){.lane,.lane .task,.app *{animation:none!important;transition:none!important}}\n";
  class ZikoTodoBoard extends HTMLElement {
    constructor(){
      super();
      this.attachShadow({mode:"open"});
      this._hass = null; this._config={}; this._items=[];
      this._loaded=false; this._fetching=false; this._busy=false;
      this._view="kanban"; this._search=""; this._project=""; this._edit=null;
      this._signature=""; this._error=""; this._lastLoaded=0;
      this.shadowRoot.addEventListener("click", e => this.onClick(e));
      this.shadowRoot.addEventListener("dragstart", e => {
        const card=e.target.closest(".task[draggable]");
        if(!card || this._busy || !e.dataTransfer)return;
        this._dragKey=card.dataset.key;
        e.dataTransfer.effectAllowed="move";
        e.dataTransfer.setData("text/plain",this._dragKey);
        card.classList.add("dragging");
      });
      this.shadowRoot.addEventListener("dragend",()=>this.clearDrag());
      this.shadowRoot.addEventListener("dragover",e=>{
        const lane=e.target.closest(".lane[data-stage]");
        if(lane&&!this._busy){e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect="move";this.shadowRoot.querySelectorAll(".lane").forEach(x=>x.classList.toggle("drop-target",x===lane));}
      });
      this.shadowRoot.addEventListener("drop",e=>{
        const lane=e.target.closest(".lane[data-stage]");if(!lane)return;
        e.preventDefault();const key=this._dragKey||(e.dataTransfer&&e.dataTransfer.getData("text/plain"));
        this.clearDrag();if(key)this.moveStage(key,lane.dataset.stage);
      });
      this.shadowRoot.addEventListener("change",e=>{
        const el=e.target.closest(".stage-select");if(el)this.moveStage(el.dataset.key,el.value);
      });
      this.shadowRoot.addEventListener("submit", e => this.onSubmit(e));
      this.shadowRoot.addEventListener("input", e => {
        if(e.target && e.target.id==="zt-search"){this._search=e.target.value;this.drawResults();}
      });
    }
    setConfig(config){ this._config=config||{}; }
    set hass(value){
      this._hass=value;
      const stamp=LISTS.map(l=>value.states[l.id] && value.states[l.id].last_updated || "?").join("|");
      if(this._loaded && stamp!==this._signature && !this._busy) this.load();
      if(!this._loaded && !this._fetching && this.isConnected) this.load();
      if(this._loaded && value.states[this._config.brand_entity||"input_text.ziko_kozponti_markanev"] && this.shadowRoot.querySelector(".brand")) {
        const brand=value.states[this._config.brand_entity||"input_text.ziko_kozponti_markanev"].state;
        const out=this.shadowRoot.querySelector(".brand .name");
        if(out && brand && out.textContent!==brand) out.textContent=brand;
      }
    }
    connectedCallback(){if(!this._loaded && this._hass) this.load();else if(!this._loaded)this.render();}
    get brand(){
      const ent=(this._hass && this._hass.states[this._config.brand_entity||"input_text.ziko_kozponti_markanev"])||null;
      return ent && ent.state && !["unknown","unavailable"].includes(ent.state)?ent.state:"Ziko™";
    }
    async load(){
      if(this._fetching || !this._hass) return;
      this._fetching=true;
      if(!this._loaded) this.render();
      try{
        const responses=await Promise.all(LISTS.map(async l=>{
          const r=await this._hass.callWS({type:"todo/item/list",entity_id:l.id});
          const list=(r && r.items) || [];
          if(!Array.isArray(list)) throw Error("A feladatlista válasza hibás: "+l.name);
          return list.map(t=>Object.assign({},t,{list:l.key,entity:l.id,key:l.key+":"+(t.uid||t.summary),meta:info(t.description,t.status==="completed")}));
        }));
        this._items=responses.flat();
        this._loaded=true; this._error=""; this._lastLoaded=Date.now();
        this._signature=LISTS.map(l=>this._hass.states[l.id] && this._hass.states[l.id].last_updated || "?").join("|");
      }catch(e){this._error=(e && e.message)||String(e);}
      finally{this._fetching=false;this.render();}
    }
    stats(){
      const active=this._items.filter(t=>t.status!=="completed");
      const today=new Date(); today.setHours(0,0,0,0);
      return {active,done:this._items.filter(t=>t.status==="completed").length,
        ai:active.filter(t=>t.list==="ai").length,human:active.filter(t=>t.list==="human").length,
        team:active.filter(t=>t.list==="team").length,
        overdue:active.filter(t=>t.due && new Date(String(t.due).slice(0,10)+"T12:00:00")<today).length};
    }
    projectNames(){
      const found=new Set(["ZIKO Technology","Házikó","ZikoTodo","Ziko Mobil"]);
      for(const t of this._items) found.add(t.meta.project);
      return Array.from(found).filter(Boolean).sort((a,b)=>a.localeCompare(b,"hu"));
    }
    filtered(){
      let arr=this._items.slice();
      if(this._view==="ai"||this._view==="human"||this._view==="team") arr=arr.filter(t=>t.list===this._view);
      if(this._view==="completed")arr=arr.filter(t=>t.status==="completed");
      else arr=arr.filter(t=>t.status!=="completed");
      if(this._project)arr=arr.filter(t=>t.meta.project===this._project);
      const term=this._search.trim().toLocaleLowerCase("hu");
      if(term) arr=arr.filter(t=>(t.summary+" "+t.meta.project+" "+t.meta.owner+" "+t.meta.note).toLocaleLowerCase("hu").includes(term));
      const rank={"Sürgős":0,"Magas":1,"Normál":2,"Alacsony":3};
      arr.sort((a,b)=>((a.due?0:1)-(b.due?0:1)) || String(a.due||"").localeCompare(String(b.due||"")) || ((rank[a.meta.priority]??2)-(rank[b.meta.priority]??2)) || a.summary.localeCompare(b.summary,"hu"));
      return arr;
    }
    card(t,kanban){
      const l=LISTS.find(l=>l.key===t.list);
      const done=t.status==="completed";
      const urgent=t.meta.priority==="Sürgős"||t.meta.priority==="Magas";
      const note=t.meta.note&&t.meta.note!==t.summary?'<div class="textnote" title="'+escapeHtml(t.meta.note)+'">'+escapeHtml(t.meta.note.slice(0,140))+'</div>':"";
      const overdue=t.due && new Date(String(t.due).slice(0,10)+"T12:00:00")<new Date(new Date().toDateString()) && !done;
      return '<article class="task'+(done?' done':'')+'"'+(kanban?' draggable="true" data-key="'+escapeHtml(t.key)+'"':'')+'>' +
        '<button class="check" data-action="toggle" data-key="'+escapeHtml(t.key)+'" aria-label="'+(done?'Újranyitás':'Készre jelölés')+'">'+(done?'✓':'')+'</button>' +
        '<div class="task-main"><div class="task-title">'+escapeHtml(t.summary)+'</div>'+
        '<div class="meta"><span class="pill '+l.color+' '+l.key+'">'+escapeHtml(l.short)+'</span>'+
        '<span class="pill">'+escapeHtml(t.meta.project)+'</span>'+
        (t.meta.owner?'<span class="pill">👤 '+escapeHtml(t.meta.owner)+'</span>':'')+
        '<span class="pill'+(urgent?' urgent':'')+'">'+escapeHtml(t.meta.priority)+'</span>'+
        (t.meta.stage && t.meta.stage!=="Beérkezett"?'<span class="pill">'+escapeHtml(t.meta.stage)+'</span>':'')+
        (t.due?'<span class="pill'+(overdue?' warn':'')+'">◷ '+dateText(t.due)+'</span>':'')+
        '</div>'+note+'</div>'+
        '<div class="task-actions"><button data-action="edit" data-key="'+escapeHtml(t.key)+'" aria-label="Szerkesztés" title="Szerkesztés">✎</button>'+
        (!done?'<button data-action="advance" data-key="'+escapeHtml(t.key)+'" aria-label="Következő munkafázis" title="Következő munkafázis">→</button>':'')+
        '</div>'+(kanban?'<select class="field stage-select" data-key="'+escapeHtml(t.key)+'" aria-label="Feladat áthelyezése">'+FLOW.map(x=>'<option value="'+escapeHtml(x)+'"'+(x===t.meta.stage?' selected':'')+'>'+escapeHtml(x)+'</option>').join('')+'</select>':'')+'</article>';
    }
    drawResults(){
      const el=this.shadowRoot.getElementById("zt-results");if(!el)return;
      if(this._view==="projects"){
        const groups={};for(const t of this.filtered())(groups[t.meta.project]||=[]).push(t);
        const html=this.projectNames().map(p=>'<button class="project" data-action="project" data-project="'+escapeHtml(p)+'"><small>PROJEKT</small><strong>'+escapeHtml(p)+'</strong><small>'+(groups[p]||[]).length+' aktív feladat · Megnyitás →</small></button>').join("");
        el.innerHTML='<div class="projects">'+html+'</div>';return;
      }
      const arr=this.filtered();
      if(this._view==="kanban"){
        const lanes=[["Beérkezett","mdi:tray-arrow-down","cyan"],["Folyamatban","mdi:progress-wrench","gold"],["Ellenőrzés","mdi:clipboard-check-outline","violet"],["Blokkolt","mdi:alert-circle-outline","rose"]];
        el.innerHTML='<div class="kanban">'+lanes.map(([stage,icon,tone])=>{
          const tasks=arr.filter(t=>t.meta.stage===stage);
          return '<section class="lane lane-'+tone+'" data-stage="'+escapeHtml(stage)+'"><h3><ha-icon icon="'+icon+'"></ha-icon><span>'+escapeHtml(stage)+'</span><b class="lane-count">'+tasks.length+'</b></h3><div class="lane-items">'+(tasks.map(t=>this.card(t,true)).join("")||'<div class="empty-lane">+ Ide húzhatsz feladatot</div>')+'</div></section>';
        }).join("")+'</div>';
        return;
      }
      el.innerHTML=arr.length?'<div class="rows">'+arr.map(t=>this.card(t,false)).join("")+'</div>':'<div class="no-items">Itt még nincs megjeleníthető feladat. Az új feladatot felül tudod felvenni.</div>';
    }
    editor(){
      const t=this._items.find(t=>t.key===this._edit);if(!t)return "";
      const options=(values,current)=>values.map(x=>'<option value="'+escapeHtml(x)+'"'+(x===current?' selected':'')+'>'+escapeHtml(x)+'</option>').join("");
      return '<form id="zt-editor" class="editor"><h3>Feladat szerkesztése</h3><div class="editor-grid">'+
      '<label class="wide">Feladat neve<input class="field" name="title" maxlength="230" required value="'+escapeHtml(t.summary)+'"></label>'+
      '<label>Projekt<input class="field" list="zt-projects" name="project" value="'+escapeHtml(t.meta.project)+'"></label>'+
      '<label>Felelős (név)<input class="field" name="owner" value="'+escapeHtml(t.meta.owner)+'"></label>'+
      '<label>Határidő<input class="field" name="due" type="date" value="'+escapeHtml(String(t.due||"").slice(0,10))+'"></label>'+
      '<label>Prioritás<select class="field" name="priority">'+options(["Alacsony","Normál","Magas","Sürgős"],t.meta.priority)+'</select></label>'+
      '<label>Állapot<select class="field" name="stage">'+options(FLOW,t.meta.stage)+'</select></label>'+
      '<label>Feladatlista<input class="field" readonly value="'+escapeHtml(LISTS.find(l=>l.key===t.list).name)+'"></label>'+
      '<label class="wide">Leírás<textarea class="field" name="note">'+escapeHtml(t.meta.note)+'</textarea></label>'+
      '</div><div class="editor-actions"><button class="primary" type="submit"'+(this._busy?' disabled':'')+'>Mentés</button><button class="secondary" data-action="close-edit" type="button">Mégse</button><button class="secondary danger" data-action="delete" data-key="'+escapeHtml(t.key)+'" type="button">Törlés…</button></div>'+
      '<div class="hint">A felelős jelenleg név szerinti megjelölés, még nem jogosultságkezelt csapattagság.</div></form>';
    }
    render(){
      if(!this.isConnected)return;
      const s=this.stats();
      const tabs=[["kanban","mdi:view-column-outline","Kanban"],["all","mdi:format-list-bulleted","Lista"],["ai","mdi:robot-outline","AI"],["human","mdi:account-outline","Saját"],["team","mdi:account-group-outline","Csapat"],["projects","mdi:folder-multiple-outline","Projektek"],["completed","mdi:check-circle-outline","Kész"]];
      const prjs=this.projectNames().map(p=>'<option value="'+escapeHtml(p)+'"></option>').join("");
      this.shadowRoot.innerHTML='<style>'+CSS+'</style><section class="app">'+
        '<header class="header"><div><div class="eyebrow"><ha-icon icon="mdi:check-decagram-outline"></ha-icon> ZIKO TECHNOLOGY / COMMAND CENTER</div><h1 class="brand"><span class="name">'+escapeHtml(this.brand)+'</span> <b>● Todo</b></h1><div class="sub">Egy helyen minden teendő · tervezés, követés, végrehajtás</div></div>'+
        '<div class="live"><span></span> LIVE · HOME ASSISTANT</div></header>'+
        '<section class="kpis"><div class="kpi cyan"><div class="label"><ha-icon icon="mdi:robot-outline"></ha-icon> AI-feladatok</div><div class="num">'+s.ai+'</div><div class="label">Nyitott</div></div>'+
        '<div class="kpi lime"><div class="label"><ha-icon icon="mdi:account-outline"></ha-icon> Saját teendők</div><div class="num">'+s.human+'</div><div class="label">Nyitott</div></div>'+
        '<div class="kpi violet"><div class="label"><ha-icon icon="mdi:account-group-outline"></ha-icon> Csapat</div><div class="num">'+s.team+'</div><div class="label">Közös lista</div></div>'+
        '<div class="kpi gold"><div class="label"><ha-icon icon="mdi:check-all"></ha-icon> Elkészült</div><div class="num">'+s.done+'</div><div class="label">'+(s.overdue?s.overdue+" lejárt határidejű":"Minden listában")+'</div></div></section>'+
        '<form class="compose" id="zt-create"><div class="comp-title">＋ ÚJ FELADAT</div><div class="compose-grid">'+
        '<input class="field fulltitle" name="title" maxlength="230" placeholder="Mit kell elvégezni?" required aria-label="Feladat neve">'+
        '<select class="field" name="list" aria-label="Feladat felelősi csoportja">'+LISTS.map(l=>'<option value="'+l.key+'">'+escapeHtml(l.short)+' · '+escapeHtml(l.name)+'</option>').join('')+'</select>'+
        '<input class="field" name="project" list="zt-projects" placeholder="Projekt (pl. Házikó)" value="ZikoTodo" aria-label="Projekt neve">'+
        '<button class="primary" type="submit"'+(this._busy?' disabled':'')+'>Hozzáadás +</button></div>'+
        '<div class="compose-extra"><input class="field" name="owner" placeholder="Felelős neve (opcionális)" aria-label="Felelős neve">'+
        '<select class="field" name="priority" aria-label="Prioritás"><option>Normál</option><option>Magas</option><option>Sürgős</option><option>Alacsony</option></select>'+
        '<input class="field" name="due" type="date" aria-label="Határidő">'+
        '<input class="field" name="note" placeholder="Rövid részletek / megjegyzés" aria-label="Feladat leírása"></div>'+
        '<datalist id="zt-projects">'+prjs+'</datalist><div class="hint">A feladat azonnal mentődik a Házikóba. Az AI-listára helyezés <b>nem</b> indít automatikus AI-munkát.</div></form>'+
        '<nav class="nav" aria-label="Feladatszűrők">'+tabs.map(p=>'<button type="button" data-action="tab" data-tab="'+p[0]+'" aria-current="'+(this._view===p[0]?'page':'false')+'"><ha-icon icon="'+p[1]+'"></ha-icon>'+p[2]+'</button>').join('')+'</nav>'+
        '<div class="tools"><input id="zt-search" class="field search" placeholder="⌕  Keresés feladatokban, projektekben..." value="'+escapeHtml(this._search)+'" aria-label="Keresés">'+
        '<div style="display:flex;gap:6px;flex-wrap:wrap;">'+(this._project?'<button class="btn" data-action="reset-project">✕ '+escapeHtml(this._project)+'</button>':'')+
        '<button class="btn" data-action="refresh">↻ Frissítés</button></div></div>'+
        (this._error?'<div class="error">Nem sikerült frissíteni az adatokat: '+escapeHtml(this._error)+'</div>':'')+
        (this._edit?this.editor():'')+
        '<div id="zt-results">'+(!this._loaded?'<div class="loading">Feladatok betöltése…</div>':'')+'</div>'+
        '<footer class="foot"><span>Valós Házikó feladatlisták · '+this._items.length+' feladat · nincs külön Vikunja-bejelentkezés</span>'+
        '<span class="footer-warn">Csapattagok jogosultságkezelése és önálló AI-futtatás: fejlesztés alatt.</span></footer>'+
        '</section>';
      if(this._loaded)this.drawResults();
    }
    async call(domain,service,data,entity){
      this._busy=true;
      try{await this._hass.callService(domain,service,data,{entity_id:entity});await this.load();}
      catch(e){this._error=e&&e.message||String(e);this.render();}
      finally{this._busy=false;this.render();}
    }
    async onSubmit(e){
      if(e.target.id==="zt-create"){
        e.preventDefault();if(this._busy)return;
        const f=new FormData(e.target),title=String(f.get("title")||"").trim();if(!title)return;
        const key=f.get("list"),list=LISTS.find(l=>l.key===key);if(!list)return;
        const meta={project:String(f.get("project")||"Általános").trim(),owner:String(f.get("owner")||"").trim(),priority:String(f.get("priority")||"Normál"),stage:"Beérkezett",note:String(f.get("note")||"").trim()};
        const data={item:title,description:description(meta)};
        if(f.get("due"))data.due_date=f.get("due");
        await this.call("todo","add_item",data,list.id);return;
      }
      if(e.target.id==="zt-editor"){
        e.preventDefault();if(this._busy)return;
        const t=this._items.find(t=>t.key===this._edit);if(!t)return;
        const f=new FormData(e.target),due=String(f.get("due")||""),stage=String(f.get("stage")||"Beérkezett");
        const data={item:t.uid||t.summary,rename:String(f.get("title")||"").trim(),description:description({project:String(f.get("project")||"Általános").trim(),owner:String(f.get("owner")||"").trim(),priority:String(f.get("priority")||"Normál"),stage,note:String(f.get("note")||"")}),status:stage==="Kész"?"completed":"needs_action"};
        if(due)data.due_date=due;
        this._edit=null;await this.call("todo","update_item",data,t.entity);return;
      }
    }
    clearDrag(){
      this._dragKey=null;
      this.shadowRoot.querySelectorAll(".lane").forEach(x=>x.classList.remove("drop-target"));
      this.shadowRoot.querySelectorAll(".dragging").forEach(x=>x.classList.remove("dragging"));
    }
    async moveStage(key,stage){
      const task=this._items.find(t=>t.key===key);
      if(!task||this._busy||!FLOW.includes(stage)||task.meta.stage===stage)return;
      this._busy=true;
      try{
        await this._hass.callService("todo","update_item",{
          item:task.uid||task.summary,
          description:description(Object.assign({},task.meta,{stage})),
          status:stage==="Kész"?"completed":"needs_action"
        },{entity_id:task.entity});
        this._error="";
        this._busy=false;
        await this.load();
      }catch(e){this._error=(e&&e.message)||String(e);}
      finally{this._busy=false;this.render();}
    }
    async onClick(e){
      const button=e.target.closest("[data-action]");if(!button)return;
      const action=button.dataset.action;
      if(action==="tab"){this._view=button.dataset.tab;this._project="";this._edit=null;this.render();return;}
      if(action==="refresh"){await this.load();return;}
      if(action==="reset-project"){this._project="";this._view="all";this.render();return;}
      if(action==="project"){this._project=button.dataset.project;this._view="all";this.render();return;}
      if(action==="close-edit"){this._edit=null;this.render();return;}
      const task=this._items.find(t=>t.key===button.dataset.key);if(!task||this._busy)return;
      if(action==="edit"){this._edit=task.key;this.render();this.shadowRoot.querySelector("#zt-editor")?.scrollIntoView({behavior:"smooth",block:"nearest"});return;}
      if(action==="toggle"){
        await this.call("todo","update_item",{item:task.uid||task.summary,status:task.status==="completed"?"needs_action":"completed"},task.entity);return;
      }
      if(action==="advance"){
        const next=task.meta.stage==="Beérkezett"?"Folyamatban":task.meta.stage==="Folyamatban"?"Ellenőrzés":task.meta.stage==="Ellenőrzés"?"Kész":"Beérkezett";
        await this.call("todo","update_item",{item:task.uid||task.summary,description:description(Object.assign({},task.meta,{stage:next})),status:next==="Kész"?"completed":"needs_action"},task.entity);return;
      }
      if(action==="delete"){
        if(!window.confirm('Biztosan törlöd ezt a feladatot? "'+task.summary+'"\nEz a művelet nem vonható vissza.'))return;
        this._edit=null;await this.call("todo","remove_item",{item:task.uid||task.summary},task.entity);
      }
    }
    getCardSize(){return 12;}
    static getStubConfig(){return {brand_entity:"input_text.ziko_kozponti_markanev"};}
  }
  customElements.define(TAG,ZikoTodoBoard);
  window.customCards=window.customCards||[];
  window.customCards.push({type:TAG,name:"ZikoTodo 0.2",description:"ZIKO feladatközpont: feladatok, projektek, Kanban, AI és csapat",preview:true});
})();