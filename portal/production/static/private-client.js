/* Private-client portal: server-scoped data only. */
(()=>{'use strict';
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let liveSync;
let sectionUpdates={counts:{},jobs:{}},badgeGeneration=0,navigationGeneration=0,navigating=false;
const sectionNames={jobs:'My jobs',quotes:'Quotes',invoices:'Invoices',attendance:'Attendance',comments:'Messages'};
const sectionTabs={jobs:['overview','activity','reports'],quotes:['quotes'],invoices:['invoices'],attendance:['attendance'],comments:['comments']};
function badge(n){return n?`<span class="client-tab-count" aria-hidden="true">(${Number(n)})</span>`:'';}
function paintBadges(){
 document.querySelectorAll('[data-client-section]').forEach(b=>{const key=b.dataset.clientSection,n=sectionUpdates.counts[key]||0;b.innerHTML=`<span>${sectionNames[key]}</span>${badge(n)}`;b.classList.toggle('has-updates',n>0);b.setAttribute('aria-label',sectionNames[key]+(n?`, ${n} new updates or items requiring attention`:''));});
 document.querySelectorAll('[data-section]').forEach(b=>{const key=b.dataset.section,n=sectionUpdates.jobs[selected?.id]?.counts[key]||0;b.innerHTML=`${sectionNames[key]}${badge(n)}`;});
 document.querySelectorAll('[data-client-job]').forEach(b=>{const n=Object.values(sectionUpdates.jobs[b.dataset.clientJob]?.counts||{}).reduce((a,b)=>a+b,0);b.innerHTML=`Open job${badge(n)}`;});
}
async function refreshBadges(){const ticket=++badgeGeneration,data=await api('private-clients/notifications/');if(ticket===badgeGeneration){sectionUpdates=data;paintBadges();}}
async function acknowledgeSection(job,key,generation){
 const ids=(sectionTabs[key]||[]).flatMap(tab=>job.tab_attention?.unread?.[tab]||[]).slice(0,1000);
 if(!ids.length)return;
 const ticket=++badgeGeneration;
 try{const data=await api('private-clients/notifications/',{job:job.id,section:key,notifications:ids});
  if(ticket===badgeGeneration){sectionUpdates=data;paintBadges();}
  if(generation===renderGeneration&&selected?.id===job.id&&section===key)for(const tab of sectionTabs[key])job.tab_attention.unread[tab]=(job.tab_attention.unread[tab]||[]).filter(id=>!ids.includes(id));
 }catch(_){notice('Your updates could not be marked as read yet. Open this section again to retry.');}
}
async function navigate(key){
 const ticket=++navigationGeneration;navigating=true;
 try{await refreshBadges();if(ticket!==navigationGeneration)return;
  if(key==='jobs'){section=key;selected=null;$('#clientMore').hidden=!next;await render();return;}
  const match=Object.entries(sectionUpdates.jobs).find(([id,j])=>j.counts[key]>0);
  const target=selected&&sectionUpdates.jobs[selected.id]?.counts[key]>0?selected.id:match?.[0]||selected?.id||jobs[0]?.id;
  const job=target&&target!==selected?.id?await api('requests/'+target+'/'):selected;
  if(ticket!==navigationGeneration)return;section=key;selected=job;await render();
 }catch(e){notice(e.message);}finally{if(ticket===navigationGeneration)navigating=false;}
}

let jobs=[],selected=null,section='jobs',page=1,next=null,renderGeneration=0;
const csrf=()=>document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.slice(10)||'';
const notice=t=>{$('#clientNotice').textContent=t;$('#clientNotice').hidden=false;};
const date=v=>v?new Date(v).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short',timeZone:'Africa/Johannesburg'}):'Not confirmed';
const money=v=>'R '+Number(v||0).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
async function api(path,values){const response=await fetch('/api/maintenance/'+path,{method:values?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),...(values?{'Idempotency-Key':crypto.randomUUID()}:{})},...(values?{body:JSON.stringify(values)}:{})});if(response.status===401){location.assign('/login/?next='+encodeURIComponent('/client/portal/'));throw Error('Please sign in.');}const data=await response.json();if(!response.ok)throw Error(data.error||'Please try again.');if(values&&path!=='private-clients/notifications/')liveSync?.nudge();return data;}
async function act(path,values){await api(path,values);if(selected)selected=await api('requests/'+selected.id+'/');await refreshBadges();await render();notice('Saved to your job.');}
async function load(){const data=await api('requests/?page='+page);jobs=page===1?data.results:jobs.concat(data.results);next=data.next;$('#clientMore').hidden=!next;}
async function open(id){const ticket=++navigationGeneration;navigating=true;try{const job=await api('requests/'+id+'/');if(ticket!==navigationGeneration)return;selected=job;await render();window.scrollTo({top:0});}finally{if(ticket===navigationGeneration)navigating=false;}}
function quoteMarkup(job){return `<div class="client-documents">${job.quotations.map(q=>`<article class="client-document"><h3>${esc(q.title)}</h3><p>${esc(q.reference)} · Revision ${q.revision} · ${esc(q.status)}</p><div class="client-amount">${money(q.amount)}</div><p>${esc(q.scope)}</p><div class="client-actions">${q.document?`<a href="${esc(q.document.download_url)}" target="_blank" rel="noreferrer">View quotation PDF</a>`:''}${q.status==='sent'&&q.can_decide!==false?`<button data-client-quote="${q.id}" data-version="${q.version}" data-decision="approved">Accept quotation</button><button class="secondary" data-client-quote="${q.id}" data-version="${q.version}" data-decision="rejected">Decline</button>`:''}</div></article>`).join('')||'<p>No quotations uploaded yet.</p>'}</div>`;}
function invoiceMarkup(job){return `<div class="client-documents">${job.invoices.map(i=>`<article class="client-document"><h3>${esc(i.number)} · ${i.purpose==='deposit'?'Deposit invoice':'Invoice'}</h3><p class="client-payment-status"><strong>${esc(i.payment_label||i.payment_status)}</strong></p><div class="client-amount">${money(i.amount)}</div><p>Outstanding: <strong>${money(i.outstanding)}</strong><br>Due: ${esc(i.due_date)}</p>${i.payment_reported?'<div class="notice">Payment reported — awaiting Sevlink verification.</div>':''}<div class="client-actions"><a href="${esc(i.document.download_url)}" target="_blank" rel="noreferrer">View invoice PDF</a><button class="secondary" data-client-payments="${i.id}">Payment history</button>${i.document_status==='active'&&!i.reconciliation_required&&Number(i.outstanding)>0&&!i.payment_reported?`<button data-client-paid="${i.id}" data-version="${i.version}">Paid</button>`:''}</div><div id="clientPayments-${i.id}" hidden>${i.payments.map(p=>`<p>Verified ${money(p.amount)} · ${esc(p.paid_on)}</p>`).join('')||'<p>No verified payments yet.</p>'}</div></article>`).join('')||'<p>No invoices uploaded yet.</p>'}</div><p>Paid reports your payment; Sevlink verifies received funds before recording them.</p>`;}
function attendanceCard(a){const confirmed=a.status==='confirmed',day=confirmed?a.agreed_date:a.requested_date,window=confirmed?a.agreed_window:a.requested_window,title=a.appointment_status==='completed'?'Completed appointment':a.appointment_status==='on_site'?'Appointment on site':a.status==='cancelled'?'Cancelled appointment':confirmed?'Confirmed appointment':a.status==='declined'?'Alternative date needed':'Requested attendance';const writtenDate=day?new Date(day+'T12:00:00+02:00').toLocaleDateString('en-ZA',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Africa/Johannesburg'}):'Call requested';return `<article class="client-document client-attendance-card"><h3>${esc(title)}</h3><h2 class="attendance-date">${esc(writtenDate)}</h2>${window?`<p class="attendance-window"><span>Arrival window</span><strong>${esc(window)}</strong><small>South African time · arrival window, not job duration</small></p>`:'<p>Call requested to arrange a suitable date.</p>'}</article>`;}

function attendanceMarkup(job){const w=job.workflow,pending=w.attendance.some(a=>a.status==='pending'),reschedule=w.attendance.some(a=>a.status==='confirmed'&&a.appointment_status==='booked'&&(a.purpose!=='assessment'||w.free_assessment));return w.attendance.map(attendanceCard).join('')+(w.can_arrange_attendance&&w.attendance_ready&&!pending&&!w.closed_at?`<form id="clientAttendance" class="client-document"><h3>${reschedule?'Need to reschedule?':'Choose a preferred attendance date'}</h3><label for="clientDate">${reschedule?'New preferred date':'Preferred date'}</label><input id="clientDate" name="date" type="date" min="${new Date().toLocaleDateString('en-CA',{timeZone:'Africa/Johannesburg'})}" required><label for="clientWindow">Preferred arrival window</label><select id="clientWindow" name="window"><option>09:00–13:00</option><option>12:00–17:00</option></select><p>${reschedule?'Your current appointment stays confirmed until Sevlink confirms the new date.':'Sevlink will confirm the final booking.'}</p><button type="submit">${reschedule?'Send reschedule request':'Send preferred date'}</button></form>`:pending?'<div class="notice">Your request is awaiting Sevlink’s confirmation.</div>':'<div class="notice">Attendance arrangements open once Sevlink authorises scheduling and any required deposit is verified.</div>');}
function commentsMarkup(job){return job.comments.map(c=>`<article class="client-message"><strong>${esc(c.actor)}</strong><p>${esc(c.text)}</p><small>${esc(date(c.at))}</small></article>`).join('')+(!job.workflow.closed_at?'<form id="clientComment" class="client-document"><label for="clientText">Message Sevlink</label><textarea id="clientText" name="text" maxlength="2500" rows="4" required></textarea><button type="submit">Send message</button></form>':'<p>This job is closed. Its records are retained.</p>');}
async function render(){const generation=++renderGeneration;document.querySelectorAll('[data-client-section]').forEach(b=>b.classList.toggle('active',b.dataset.clientSection===section));
if(!selected){$('#clientContent').innerHTML='<div class="client-panel-title"><h2>Your jobs</h2><span>Private client</span></div>'+jobs.map(j=>`<article class="client-job"><span class="private-client-badge">PRIVATE CLIENT</span><h2>${esc(j.title)}</h2><p>${esc(j.property.address)}<br>${esc(j.reference)} · ${esc(j.status_label)}</p><button data-client-job="${j.id}">Open job</button></article>`).join('')+(jobs.length?'':'<p>No jobs are currently available.</p>');}
else{const job=selected;$('#clientMore').hidden=true;$('#clientContent').innerHTML=`<button class="secondary client-back" id="clientBack">← All my jobs</button><article class="client-job"><span class="private-client-badge">PRIVATE CLIENT</span><h2>${esc(job.title)}</h2><p>${esc(job.property.address)} · ${esc(job.reference)}</p>${section==='jobs'?`<p>${esc(job.description)}</p><p>Status: ${esc(job.status_label)}</p>${job.workflow.additional.filter(a=>a.status==='pending').map(a=>`<div class="notice"><strong>Additional call-out authorisation: ${money(a.amount)}</strong><p>${esc(a.reason)}</p><button data-client-extra="${a.id}" data-choice="approved">Approve total</button> <button class="secondary" data-client-extra="${a.id}" data-choice="declined">Decline</button> <button class="secondary" data-client-extra="${a.id}" data-choice="quotation">Request separate quotation</button></div>`).join('')}<div class="client-actions"><button data-section="quotes">Quotes</button><button data-section="invoices">Invoices</button><button data-section="attendance">Attendance</button><button data-section="comments">Messages</button></div>${job.attachments.length?'<h3>Photos and reports</h3><div class="client-actions">'+job.attachments.map(a=>`<a href="${esc(a.download_url)}" target="_blank" rel="noreferrer">${esc(a.filename)}</a>`).join('')+'</div>':''}`:section==='quotes'?quoteMarkup(job):section==='invoices'?invoiceMarkup(job):section==='attendance'?attendanceMarkup(job):commentsMarkup(job)}</article>`;
$('#clientBack').onclick=()=>{++navigationGeneration;navigating=false;selected=null;$('#clientMore').hidden=!next;render();};
$('#clientAttendance')?.addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));await act(`requests/${job.id}/workflow/attendance-request/`,{version:job.version,preference:'date',...d});}catch(error){notice(error.message);b.disabled=false;}});
$('#clientComment')?.addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await act(`requests/${job.id}/comments/`,{text:new FormData(e.target).get('text'),visibility:'shared'});}catch(error){notice(error.message);b.disabled=false;}});
}
if(generation!==renderGeneration)return;
document.querySelectorAll('[data-client-job]').forEach(b=>b.onclick=()=>open(b.dataset.clientJob).catch(e=>notice(e.message)));
document.querySelectorAll('[data-section]').forEach(b=>b.onclick=()=>navigate(b.dataset.section));
document.querySelectorAll('[data-client-quote]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const reason=b.dataset.decision==='rejected'?prompt('Reason or comment (optional):',''):'';if(reason===null){b.disabled=false;return;}await act(`requests/${selected.id}/quotations/${b.dataset.clientQuote}/decision/`,{version:Number(b.dataset.version),status:b.dataset.decision,reason});}catch(e){notice(e.message);b.disabled=false;}});
document.querySelectorAll('[data-client-extra]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await act(`requests/${selected.id}/workflow/additional-decision/`,{version:selected.version,additional:Number(b.dataset.clientExtra),decision:b.dataset.choice});}catch(e){notice(e.message);b.disabled=false;}});
document.querySelectorAll('[data-client-paid]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await act(`requests/${selected.id}/invoices/${b.dataset.clientPaid}/report-paid/`,{version:Number(b.dataset.version)});}catch(e){notice(e.message);b.disabled=false;}});
document.querySelectorAll('[data-client-payments]').forEach(b=>b.onclick=()=>{const panel=$('#clientPayments-'+b.dataset.clientPayments);panel.hidden=!panel.hidden;});
paintBadges();
if(selected&&generation===renderGeneration)await acknowledgeSection(selected,section,generation);
}
document.querySelectorAll('[data-client-section]').forEach(b=>b.onclick=()=>navigate(b.dataset.clientSection));
$('#clientMore').onclick=async()=>{page=next;try{await load();render();}catch(e){notice(e.message);}};
for(const type of ['input','change'])document.addEventListener(type,event=>{const form=event.target.closest('form');if(form)form.dataset.liveDirty='true';});
async function applyLiveUpdate(){
 await refreshBadges();
 if(navigating)return false;
 const content=$('#clientContent');
 if(content.querySelector('form[data-live-dirty]')||(content.contains(document.activeElement)&&document.activeElement.matches('input,textarea,select')))return false;
 const id=selected?.id,active=section,loadedPage=page,position={x:scrollX,y:scrollY};let fresh=[],last;
 for(let i=1;i<=loadedPage;i++){last=await api('requests/?page='+i);fresh=fresh.concat(last.results);if(!last.next)break;}
 const job=id?await api('requests/'+id+'/'):null;
 if(active!==section||id!==selected?.id||loadedPage!==page)return false;
 if(content.querySelector('form[data-live-dirty]')||(content.contains(document.activeElement)&&document.activeElement.matches('input,textarea,select')))return false;
 jobs=fresh;next=last.next;selected=job;$('#clientMore').hidden=!next;await render();window.scrollTo(position.x,position.y);return true;
}
(async()=>{try{const context=await api('context/');if(context.user.role!=='client')throw Error('Private-client access required.');await refreshBadges();await load();const params=new URLSearchParams(location.search);if(['jobs','quotes','invoices','attendance','comments'].includes(params.get('section')))section=params.get('section');const id=params.get('job');if(id)await open(id);else await render();liveSync=window.SevlinkLiveSync?.start({read:()=>api('live-revision/'),update:applyLiveUpdate});}catch(e){notice(e.message);}})();
})();
