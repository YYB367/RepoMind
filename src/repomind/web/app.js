"use strict";
const $ = (id) => document.getElementById(id);
const memoryPage = location.pathname === "/memories";
const states = {pending:"待确认", confirmed:"已确认", rejected:"已拒绝", ok:"有效事实", unknown:"仅有计划", insufficient_evidence:"事实冲突"};
const types = {declare:"声明事实", plan:"计划", complete:"已完成"};
const reasons = {latest_effective_fact:"根据所选日期的有效事实得出。", only_plans:"记录了计划，尚无完成事实。", conflicting_effective_facts:"同一生效时间存在不同事实，证据不足以确定唯一答案。"};
let items = [], selected = null, offset = 0, total = 0, sequence = 0, busy = false, viewProject = "";
const limit = 30;
const node = (tag, text, className) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (className) e.className = className; return e; };
const stamp = (value) => value ? new Date(value).toLocaleString("zh-CN", {timeZone:"UTC", hour12:false}) + " UTC" : "未记录";
const shortDate = (value) => value ? value.slice(0,10) : "";
const badge = (state) => node("span", states[state] || state, "badge " + state);
function notice(message="", kind="") { $("notice").textContent=message; $("notice").className="notice " + kind; }
async function api(url, body) {
  const options = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json", "X-RepoMind-CSRF":document.querySelector('meta[name="repomind-csrf"]').content}, body:JSON.stringify(body)};
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || "读取失败，请刷新后重试。"); error.status=response.status; throw error; }
  return data;
}
function dirty() {
  if (memoryPage || !selected || selected.status!=="pending" || !$("edit-value")) return false;
  return $("edit-value").value!==selected.draft.value || $("edit-type").value!==selected.draft.event_type || $("edit-effective").value!==selected.draft.effective_at;
}
function canLeave() { return !dirty() || window.confirm("修改尚未保存，是否放弃修改？"); }
function updateLinks() {
  for (const [id,path] of [["review-link","/review"],["memories-link","/memories"]]) $(id).href=path+"?project="+encodeURIComponent($("project").value.trim());
  $("tasks-link").href="/tasks?project="+encodeURIComponent($("project").value.trim());
}
function params() {
  const p = new URLSearchParams({project:$("project").value.trim(), q:$("query").value.trim(), offset, limit});
  if (memoryPage) { p.set("as_of",$("as-of").value); if ($("known-at").value) p.set("known_at",$("known-at").value); }
  else p.set("status",$("status").value);
  return p;
}
async function load(keep=null, success="") {
  const request=++sequence;
  const filters=params();
  $("record-list").setAttribute("aria-busy","true");
  $("record-list").replaceChildren(node("p","正在读取记忆库…","empty"));
  $("previous").disabled=true; $("next").disabled=true;
  selected=null; $("detail").replaceChildren(node("p","选择一条记录，核对事实与来源。","empty"));
  notice(); updateLinks();
  try {
    const result=await api((memoryPage?"/api/memories?":"/api/candidates?")+filters);
    if (request!==sequence) return;
    items=result.items; total=result.total; viewProject=filters.get("project");
    $("count").textContent=total+" 条";
    $("counts").textContent=result.counts ? `待确认 ${result.counts.pending}　已确认 ${result.counts.confirmed}　已拒绝 ${result.counts.rejected}` : "";
    renderList();
    if (keep) select(items.find(r=>r.candidate_id===keep.candidate_id) || keep);
    const url=new URLSearchParams(filters); url.delete("limit"); history.replaceState(null,"",location.pathname+"?"+url);
    if (success) notice(success,"success");
  } catch(error) {
    if(request!==sequence) return;
    $("count").textContent="读取失败"; $("counts").textContent="";
    $("record-list").replaceChildren(node("p","未能读取记录。检查项目和日期，或点击刷新记录重试。","empty"));
    notice(error.message,"error");
  } finally { if(request===sequence) $("record-list").setAttribute("aria-busy","false"); }
}
function renderList() {
  const list=$("record-list"); list.replaceChildren();
  if (!items.length) list.append(node("p",memoryPage?"此项目与日期下没有匹配记忆。可调整搜索和日期，或先确认候选。":"没有匹配候选。可切换审核状态，或通过 review propose / Codex 任务生成候选。","empty"));
  items.forEach((row)=>{
    const draft=memoryPage?{subject:row.subject,predicate:row.field,value:row.value || row.sources.map(s=>s.event.value).join(" / ")}:row.draft;
    const button=node("button",undefined,"record"); button.type="button"; button.setAttribute("aria-pressed",String(selected===row));
    button.append(node("span",draft.subject+" / "+draft.predicate,"record-key"),node("span",draft.value,"record-value"));
    const bottom=node("span",undefined,"record-bottom"); bottom.append(badge(row.status),node("span",memoryPage?"查看来源":shortDate(row.artifact.recorded_at))); button.append(bottom);
    button.addEventListener("click",()=>{if(!busy && canLeave()) {select(row); if(innerWidth<621) {$("detail").scrollIntoView({block:"start"}); $("detail").focus({preventScroll:true});}}});
    list.append(button);
  });
  $("page-info").textContent=total?`${offset+1}–${Math.min(offset+limit,total)} / ${total}`:"0 条";
  $("previous").disabled=offset===0; $("next").disabled=offset+limit>=total;
}
function meta(rows) { const dl=node("dl",undefined,"meta"); rows.forEach(([label,value])=>{dl.append(node("dt",label),node("dd",String(value ?? "未记录")));}); return dl; }
function source(artifact,quote,extra=[]) {
  const group=node("section",undefined,"source-group");
  const evidence=node("div",undefined,"evidence"); evidence.append(node("h3","原文证据"),node("blockquote",quote || "此旧记录未保存原文引文。")); group.append(evidence);
  if(artifact) group.append(meta([["来源路径",artifact.path],["记录时间",stamp(artifact.recorded_at)]]));
  const details=node("details"); details.append(node("summary","查看来源标识与摘要"));
  const rows=artifact?[["来源类型",artifact.kind==="git"?"Git 提交":"文件记录"],["Git 提交",artifact.commit || "无"],["SHA-256",artifact.sha256]]: [["来源说明","此旧记录无审核时保存的文件定位；可通过来源 ID 核对。"]];
  details.append(meta([...rows,...extra])); group.append(details); return group;
}
function select(row) { selected=row; renderList(); if(memoryPage) renderMemory(row); else renderCandidate(row); }
function heading(key,state) {
  const h=node("div",undefined,"detail-heading"); const text=node("div"); text.append(node("p",viewProject,"fact-key"),node("h2",key)); h.append(text,badge(state)); return h;
}
function renderCandidate(row) {
  const panel=$("detail"); panel.replaceChildren(heading(row.draft.subject+" / "+row.draft.predicate,row.status));
  if(row.status!=="pending") panel.append(node("p",row.status==="confirmed"?"已写入正式记忆。命令行与新会话可读取同一记录。":"已拒绝。此候选不会进入正式记忆或跨会话召回。","state-note "+row.status));
  if(row.status==="pending") {
    const label=node("label","事实内容"); const value=node("textarea"); value.id="edit-value"; value.value=row.draft.value; value.maxLength=4000; value.rows=3; label.append(value); panel.append(label);
    const grid=node("div",undefined,"edit-grid");
    const typeLabel=node("label","记录类型"); const type=node("select"); type.id="edit-type";
    Object.entries(types).forEach(([key,text])=>{const option=node("option",text);option.value=key;type.append(option);});type.value=row.draft.event_type;typeLabel.append(type);
    const whenLabel=node("label","生效时间（含时区）"); const when=node("input"); when.id="edit-effective"; when.value=row.draft.effective_at; when.placeholder="2026-11-07T00:00:00Z"; whenLabel.append(when);
    grid.append(typeLabel,whenLabel); panel.append(grid);
  } else panel.append(node("p",row.draft.value,"fact-value"),meta([["记录类型",types[row.draft.event_type]],["生效时间",stamp(row.draft.effective_at)],["审核时间",stamp(row.reviewed_at)]]));
  panel.append(source(row.artifact,row.quote,[["候选 ID",row.candidate_id],["来源 ID",row.draft.source_id],["审核版本",row.revision]]));
  panel.append(node("p",row.rationale||"此记录未保存助手理由。请依据已保存引文与来源版本核对事实。","decision-note"));
  attachPreview(row,panel);
  if(row.status==="pending") {
    const actions=node("div",undefined,"actions");
    const save=node("button","保存修改","quiet");save.id="save-edit";save.type="button";save.disabled=true;save.addEventListener("click",()=>mutate("edit"));
    const confirm=node("button","确认写入","primary");confirm.id="confirm-candidate";confirm.type="button";confirm.addEventListener("click",()=>decision("confirm"));
    const reject=node("button","拒绝候选","danger");reject.id="reject-candidate";reject.type="button";reject.addEventListener("click",()=>decision("reject"));
    actions.append(save,confirm,reject);panel.append(actions,node("p",`当前审核版本 ${row.revision}。修改后先保存，再确认写入。`,"decision-note"));
    for(const id of ["edit-value","edit-type","edit-effective"]) $(id).addEventListener("input",()=>{$("save-edit").disabled=!dirty();confirm.disabled=dirty();reject.disabled=dirty();});
  }
}
function renderMemory(row) {
  const panel=$("detail");panel.replaceChildren(heading(row.subject+" / "+row.field,row.status));
  panel.append(node("p",row.value || (row.status==="unknown"?"尚无完成事实":"无法确定唯一事实"),"fact-value"),node("p",reasons[row.reason] || row.reason,"result-note"));
  row.sources.forEach(s=>{panel.append(meta([["事件类型",types[s.event.event_type] || s.event.event_type],["事件内容",s.event.value],["生效时间",stamp(s.event.effective_at)],["获知时间",stamp(s.event.observed_at)]]));panel.append(source(s.artifact,s.provenance?.evidence_text || s.record?.text,[["事件 ID",s.event.event_id],["来源 ID",s.event.source_id]]));});
}
function decision(action) {
  if(busy || dirty()) return;
  const confirm=action==="confirm";
  $("decision-title").textContent=confirm?"确认写入正式记忆":"拒绝这条候选";
  $("decision-copy").textContent=confirm?"请核对以下事实及来源。写入后，新任务可以按项目召回这条记忆。":"拒绝后不会写入正式记忆。这条候选将保留在审核历史中。";
  $("decision-summary").textContent=`${selected.draft.project_id} / ${selected.draft.subject} / ${selected.draft.predicate}\n${selected.draft.value}\n\n审核版本 ${selected.revision}\n${selected.artifact.path}`;
  $("decision-submit").textContent=confirm?"确认写入正式记忆":"确认拒绝候选";
  $("decision-submit").className=confirm?"primary":"danger";
  $("decision-dialog").returnValue=""; $("decision-dialog").dataset.action=action; $("decision-dialog").showModal();
}
async function mutate(action) {
  if(busy || !selected) return;
  busy=true; const row=selected;
  const body={project:row.draft.project_id,revision:row.revision};
  if(action==="edit") Object.assign(body,{value:$("edit-value").value,event_type:$("edit-type").value,effective_at:$("edit-effective").value});
  document.querySelectorAll("button,input,select,textarea").forEach(e=>e.disabled=true); notice("正在保存…");
  try {
    const saved=await api(`/api/candidates/${row.candidate_id}/${action}`,body);
    await load(saved,action==="confirm"?"已确认写入正式记忆。":action==="reject"?"已拒绝候选。":"修改已保存，请重新核对事实与来源。");
  } catch(error) {
    if(error.status===409 || error.status===404) await load();
    notice(error.message,"error");
  } finally {
    busy=false;document.querySelectorAll("button,input,select,textarea").forEach(e=>e.disabled=false);
    if(selected && !memoryPage && selected.status==="pending") {
      $("save-edit").disabled=!dirty();$("confirm-candidate").disabled=dirty();$("reject-candidate").disabled=dirty();
    }
    $("previous").disabled=offset===0;$("next").disabled=offset+limit>=total;
  }
}
$("decision-dialog").addEventListener("close",()=>{if($("decision-dialog").returnValue==="proceed") mutate($("decision-dialog").dataset.action);});
$("filters").addEventListener("submit",event=>{event.preventDefault();if(!busy && canLeave()){offset=0;load();}});
$("refresh").addEventListener("click",()=>{if(!busy && canLeave())load();});
$("previous").addEventListener("click",()=>{if(!busy && canLeave()){offset=Math.max(0,offset-limit);load();}});
$("next").addEventListener("click",()=>{if(!busy && canLeave()){offset+=limit;load();}});
for(const id of ["tasks-link","review-link","memories-link"]) $(id).addEventListener("click",event=>{if(busy || !canLeave())event.preventDefault();});
window.addEventListener("beforeunload",event=>{if(dirty()){event.preventDefault();event.returnValue="";}});
async function init() {
  const initial=new URLSearchParams(location.search);
  $(memoryPage?"memories-link":"review-link").setAttribute("aria-current","page");
  $("date-filter").hidden=!memoryPage;$("known-filter").hidden=!memoryPage;$("date-help").hidden=!memoryPage;$("status-filter").hidden=memoryPage;
  if(memoryPage) {document.title="项目记忆 · RepoMind";$("page-title").textContent="项目记忆";$("page-description").textContent="按项目与日期查询事实，随时回到决策的来源。";$("list-title").textContent="记忆记录";}
  $("as-of").value=initial.get("as_of") || new Date().toISOString().slice(0,10);
  $("known-at").value=initial.get("known_at") || "";$("query").value=initial.get("q") || "";
  $("status").value=["pending","confirmed","rejected","all"].includes(initial.get("status"))?initial.get("status"):"pending";
  $("project").value=initial.get("project") || "RepoMind";
  try {const result=await api("/api/projects");result.projects.forEach(p=>{const o=node("option");o.value=p;$("projects").append(o);});if(!initial.has("project"))$("project").value=result.default_project;} catch(error){notice(error.message,"error");}
  await load();
  if(!memoryPage && initial.get("candidate")) {
    try {select(await api("/api/candidates/"+encodeURIComponent(initial.get("candidate"))+"?project="+encodeURIComponent($("project").value.trim())));}catch(error){notice(error.message,"error");}
  }
}
function attachPreview(row,panel) {
  const area=node("section",undefined,"file-preview");panel.append(area);
  async function read() {
    area.replaceChildren(node("h3","来源文件预览"),node("p","正在读取候选绑定版本…","help"));
    try {
      const data=await api("/api/candidates/"+row.candidate_id+"/preview?project="+encodeURIComponent(row.draft.project_id));
      if(selected!==row || !area.isConnected)return;
      area.replaceChildren(node("h3","来源文件预览"));
      const scopes={quote:"仅保存引文",git:"Git 提交版本",file:"当前文件（摘要匹配）",task_snapshot:"任务结束快照"};
      area.append(node("p",scopes[data.scope]+" · "+(data.commit||data.expected_sha256),"help"));
      if(data.warning)area.append(node("p",data.warning,"preview-warning"));
      const body=node("pre",undefined,"code-view");let full=false;
      const toggle=node("button","显示完整正文","quiet");toggle.type="button";
      function paint(){let text=data.text;const at=text.indexOf(data.quote);if(!full && at>=0 && data.scope!=="quote") {const start=Math.max(0,text.lastIndexOf("\n",Math.max(0,at-450)));const end=text.indexOf("\n",at+data.quote.length+450);text=text.slice(start,end<0?text.length:end);}
        body.replaceChildren();const i=text.indexOf(data.quote);if(i>=0){body.append(document.createTextNode(text.slice(0,i)),node("mark",data.quote),document.createTextNode(text.slice(i+data.quote.length)));}else body.textContent=text;
        toggle.textContent=full?"仅显示引文前后文":"显示完整正文";
      }
      toggle.onclick=()=>{full=!full;paint();};paint();area.append(body);if(data.scope!=="quote")area.append(toggle);
      for(const change of data.changes){const d=node("details");d.append(node("summary","本次任务差异："+change.path),node("pre",change.diff||"此文件无法完整生成差异。","code-view diff-view"));area.append(d);}
    }catch(error){area.replaceChildren(node("h3","来源文件预览"),node("p",error.message+" 编辑内容已保留。","notice error"));}
    const retry=node("button","重新读取来源","quiet");retry.type="button";retry.onclick=read;area.append(retry);
  }
  read();
}
init();
