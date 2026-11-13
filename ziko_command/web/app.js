"use strict";
const $=id=>document.getElementById(id);
const state={lastRefresh:0,pending:false};

async function readJson(path,init){
 const response=await fetch(path,Object.assign({credentials:"same-origin",cache:"no-store"},init||{}));
 let value;
 try{value=await response.json()}catch{throw Error("A Command nem küldött érvényes JSON-választ.")}
 if(!response.ok)throw Error(value.error||("HTTP "+response.status));
 return value;
}

function text(id,value){$(id).textContent=String(value==null?"":value);}
function showNotice(message,error=false){const el=$("notice");el.textContent=message;el.classList.toggle("error",error);}
function formatDate(timestamp){
 if(!timestamp)return "Még nincs adat";
 return new Date(timestamp*1000).toLocaleString("hu-HU",{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
}

async function refreshStatus(){
 try{
  const v=await readJson("api/status");
  text("engine-state",v.service==="active"?"Működik":"Ellenőrzendő");
  text("pulse-title",v.service==="active"?"Command üzemel":"Ellenőrizendő");
  $("pulse-dot").classList.toggle("online",v.service==="active");
  $("pulse-dot").classList.toggle("offline",v.service!=="active");
  text("ai-state",v.ai_executor_connected?"Kapcsolódott":"Nincs csatlakoztatva");
  text("todo-state",v.todo_linked?"Kapcsolódott":"Bekötés alatt");
  text("digest-time","19:00");
  text("last-heartbeat",v.last_heartbeat_at?"Utolsó életjel: "+formatDate(v.last_heartbeat_at):"Nincs életjel");
  text("executor-detail",v.ai_executor_connected?"Végrehajtó elérhető":"A Ziko AI bekötése folyamatban");
  text("digest-detail","19:00 · a jelentés helyben elkészül, push még nincs");
 }catch(error){text("engine-state","Kapcsolati hiba");text("pulse-title","Nem elérhető");$("pulse-dot").classList.add("offline");showNotice("Állapotlekérés: "+error.message,true);}
}

async function refreshMessages(){
 try{
  const result=await readJson("api/messages");
  const list=Array.isArray(result.messages)?result.messages:[];
  text("inbox-count",list.length+" üzenet");
  const feed=$("feed");feed.replaceChildren();
  if(!list.length){
   const empty=document.createElement("div");empty.className="placeholder";
   empty.textContent="Itt gyűlnek a parancsnoknak küldött üzeneteid. Az AI-kapcsolat bekötéséig tartós, visszaolvasható munkabeérkezésként működik.";
   feed.append(empty);return;
  }
  for(const message of list){
   const article=document.createElement("article");article.className="msg";
   const head=document.createElement("div");head.className="msgHeader";
   const from=document.createElement("span");from.textContent="◈ TE · ZIKÓNAK";
   const at=document.createElement("time");at.textContent=formatDate(message.created_at);
   head.append(from,at);
   const body=document.createElement("div");body.className="body";
   body.textContent=message.text||"";
   const meta=document.createElement("div");meta.className="meta";
   meta.textContent=message.status==="awaiting_ai"?"⏳ Rögzítve · Ziko AI kapcsolatra vár":"Állapot: "+message.status;
   article.append(head,body,meta);
   feed.append(article);
  }
 }catch(error){showNotice("Üzenetek olvasása: "+error.message,true);}
}

async function submitMessage(event){
 event.preventDefault();
 if(state.pending)return;
 const field=$("message"),body=field.value.trim();
 if(!body)return;
 state.pending=true;$("send").disabled=true;showNotice("Parancs rögzítése…");
 try{
  const clientKey=(typeof crypto!=="undefined"&&crypto.randomUUID)?crypto.randomUUID():"m"+Date.now().toString(36);
  const result=await readJson("api/messages",{
   method:"POST",
   headers:{"Content-Type":"application/json","X-Ziko-Request":"1"},
   body:JSON.stringify({text:body,client_key:clientKey}),
  });
  field.value="";
  showNotice(result.note||"Parancs beérkezett.");
  await refreshMessages();
 }catch(error){showNotice("Nem sikerült rögzíteni: "+error.message,true);}
 finally{state.pending=false;$("send").disabled=false;}
}

$("form").addEventListener("submit",submitMessage);
$("message").addEventListener("keydown",event=>{
 if((event.ctrlKey||event.metaKey)&&event.key==="Enter"){
  event.preventDefault();$("form").requestSubmit();
 }
});

async function refresh(){
 if(document.hidden)return;
 await Promise.all([refreshStatus(),refreshMessages()]);
 state.lastRefresh=Date.now();
}
refresh();
setInterval(()=>{if(!document.hidden)refreshStatus();},30000);
document.addEventListener("visibilitychange",()=>{
 if(!document.hidden&&Date.now()-state.lastRefresh>15000)refresh();
});
