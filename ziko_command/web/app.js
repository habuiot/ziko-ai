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
   const answers=document.createElement("div");answers.className="msgReplies";
   for(const reply of Array.isArray(message.replies)?message.replies:[]){
    const item=document.createElement("p");item.className="msgReply";
    item.textContent="TE · "+(reply.text||"");
    answers.append(item);
   }
   const replyButton=document.createElement("button");
   replyButton.type="button";replyButton.className="reply-control";
   replyButton.textContent="Válasz Zikónak";
   const replyForm=document.createElement("form");replyForm.className="replyComposer";
   replyForm.hidden=true;
   const replyInput=document.createElement("textarea");
   replyInput.maxLength=1200;replyInput.rows=2;replyInput.required=true;
   replyInput.placeholder="Egyeztetés vagy válasz a korábbi üzenethez…";
   const replySend=document.createElement("button");replySend.type="submit";
   replySend.textContent="Válasz mentése";
   replyForm.append(replyInput,replySend);
   replyButton.addEventListener("click",()=>{
    replyForm.hidden=!replyForm.hidden;
    if(!replyForm.hidden)replyInput.focus();
   });
   replyForm.addEventListener("submit",async event=>{
    event.preventDefault();
    const value=replyInput.value.trim();if(!value)return;
    replySend.disabled=true;
    try{
     const key=(typeof crypto!=="undefined"&&crypto.randomUUID)?
       crypto.randomUUID():"reply"+Date.now().toString(36);
     const result=await readJson("api/messages/replies",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-Ziko-Request":"1"},
      body:JSON.stringify({parent_id:message.id,text:value,client_key:key})
     });
     showNotice(result.note||"A válasz mentve.");
     await refreshMessages();
    }catch(error){showNotice("Válasz: "+error.message,true);}
    finally{replySend.disabled=false;}
   });
   article.append(head,body,meta,answers,replyButton,replyForm);
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


function addWfText(parent,tag,value,className){
 const el=document.createElement(tag);
 if(className)el.className=className;
 el.textContent=String(value==null?"":value);
 parent.append(el);
 return el;
}
async function refreshWorkflow(){
 const roles=$("wf-agents"),jobs=$("wf-jobs");
 try{
  const answer=await readJson("api/work");
  const data=answer.workflow||{};
  roles.replaceChildren();jobs.replaceChildren();
  text("wf-state",String(data.job_count||0)+" feladat · "+(data.model_state==="not_installed"?"Helyi AI nincs":data.model_state||"Nem ismert"));
  for(const agent of Array.isArray(data.roles)?data.roles:[]){
   const card=document.createElement("div");card.className="wf-agent";
   addWfText(card,"strong",agent.role||agent.role_id||"Ügynök");
   addWfText(card,"small",agent.confirmed_active?"Aktív (igazolt)":"Nem aktív");
   roles.append(card);
  }
  for(const job of Array.isArray(data.jobs)?data.jobs:[]){
   const card=document.createElement("article");card.className="wf-job";
   const side=document.createElement("div");
   addWfText(side,"strong",job.work_id||job.project_id||job.job_id);
   addWfText(side,"small",(job.phase_label||job.phase||"")+
      (job.scheduler_gate?" · "+job.scheduler_gate:""));
   card.append(side);
   if(job.phase==="meeting_ready"&&!job.approved&&job.artifact_sha&&answer.approval_ready){
    const button=addWfText(card,"button","Elfogadom","wf-approve");
    button.type="button";
    button.addEventListener("click",()=>approveWorkflow(job,button));
   }
   jobs.append(card);
  }
  if(!data.jobs||!data.jobs.length) addWfText(jobs,"div","Nincs aktív Workflow-feladat.","wf-status");
 }catch(error){
  roles.replaceChildren();jobs.replaceChildren();
  text("wf-state",error.message==="workflow_feed_unavailable"?"Workflow-forrás nem elérhető":
       error.message==="owner_only"?"Tulajdonosi hozzáférés szükséges":
       "Workflow: "+error.message);
 }
}
async function approveWorkflow(job,button){
 const shortHash=job.artifact_sha.slice(0,12);
 if(!window.confirm("Elfogadod a "+job.work_id+" feladat "+shortHash+"… verzióját?"))return;
 button.disabled=true;
 try{
  const r=await readJson("api/work/approve",{
   method:"POST",
   headers:{"Content-Type":"application/json","X-Ziko-Request":"1"},
   body:JSON.stringify({job_id:job.job_id,artifact_sha:job.artifact_sha})
  });
  text("wf-state",r.state==="approval_recorded_not_deployed"?
      "Döntés rögzítve. Élesítés nem indult.":"Döntés ellenőrzése szükséges");
  await refreshWorkflow();
 }catch(error){
  text("wf-state","Jóváhagyás sikertelen: "+error.message);
 }finally{button.disabled=false;}
}
$("wf-refresh").addEventListener("click",refreshWorkflow);

async function refresh(){
 if(document.hidden)return;
 await Promise.all([refreshStatus(),refreshMessages(),refreshWorkflow()]);
 state.lastRefresh=Date.now();
}
refresh();
setInterval(()=>{if(!document.hidden){refreshStatus();refreshWorkflow();}},30000);
document.addEventListener("visibilitychange",()=>{
 if(!document.hidden&&Date.now()-state.lastRefresh>15000)refresh();
});

