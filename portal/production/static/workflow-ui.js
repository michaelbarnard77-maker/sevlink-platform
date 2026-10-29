/* Real Django workflow presentation; no localStorage, sample records or operational simulation. */
window.SevlinkWorkflowUI = (() => {
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function photoPicker(input,existingBytes=0){
    if(!input)return;let selected=[];
    const list=document.createElement('div');list.className='photo-selection';const error=document.createElement('p');error.setAttribute('role','alert');error.hidden=true;input.after(list,error);
    const sync=()=>{const transfer=new DataTransfer();selected.forEach(f=>transfer.items.add(f));input.files=transfer.files;list.replaceChildren();
      if(selected.length){const total=document.createElement('p');total.textContent=`${selected.length} selected · ${(selected.reduce((n,f)=>n+f.size,0)/1024/1024).toFixed(2)} MB`;list.append(total);}
      selected.forEach((f,index)=>{const row=document.createElement('div');row.className='toolbar';const name=document.createElement('span');name.style.flex='1';name.textContent=f.name;const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='Remove photo';remove.onclick=()=>{selected.splice(index,1);error.hidden=true;input.setCustomValidity('');sync();};row.append(name,remove);list.append(row);});if(selected.length||!error.hidden){const clear=document.createElement('button');clear.type='button';clear.className='secondary';clear.textContent='Clear photo selection';clear.onclick=()=>{selected=[];error.hidden=true;input.setCustomValidity('');sync();};list.append(clear);}
    };
    input.onchange=()=>{const candidate=[...selected];for(const f of input.files){if(!candidate.includes(f))candidate.push(f);}
      const message=candidate.some(f=>f.size===0)?'Empty files cannot be uploaded.':candidate.some(f=>f.size>5*1024*1024)?'Each photo must be 5 MB or less.':existingBytes+candidate.reduce((n,f)=>n+f.size,0)>25*1024*1024?'Photos and documents for this repair must total 25 MB or less.':'';
      input.setCustomValidity(message);if(message){error.textContent=message;error.hidden=false;}else{selected=candidate;error.hidden=true;}sync();
    };
  }
  const paths=[
    'M4 9h12v5a4 4 0 0 1-8 0V9m4-5v5m4-3h4v4h-4M4 7v4',
    'm13 2-9 12h7l-1 8 10-13h-7z',
    'M4 22V3h13v19M8 22V7h9M13 14h1m4-5h4v7h-4m1-7V7a1 1 0 0 1 2 0v2',
    'M4 3h12v5H4zM16 5h4v8h-9v8',
    'M3 3h18v18H3zM3 12h18M12 3v18',
    'm14 6 4-4 4 4-4 4-3-1-10 12-3-3L14 7z',
    'm2 12 10-9 10 9M5 10v11h14V10M8 7l12 4M6 14h12',
    'M3 4h15v5H3zM17 9v5h4v7M8 4V2M4 9v4h9',
    'M12 2s-7 8-7 13a7 7 0 0 0 14 0c0-5-7-13-7-13zM8 15a4 4 0 0 0 4 4',
    'M2 4h20M5 4v4h14V4M3 13h18M6 13v8M12 13v8M18 13v8',
    'M3 21V3h18v18M3 12h18M12 3v18M8 8h1m6 8h1',
    'M3 3h18v18H3zM12 3v18M3 12h18M6 9l3-3m6 12 3-3',
    'm2 9 10-7 10 7M4 9h16v13H4zM4 13h16M4 17h16',
    'M4 2h16v20H4zM4 8h16M8 5h1M8 12h1m3-3v12',
    'M2 4h20v8H2zM5 8h14M7 16v5m5-5v6m5-6v5',
    'M12 22V11M12 14C2 14 2 4 2 4s10 0 10 10m0 3c10 0 10-10 10-10s-10 0-10 10',
    'M9 4h6l3 6v9l-6 3-6-3v-9zM9 3 6 1m9 2 3-2M3 9h4m10 0h4M2 15h5m10 0h5M3 21l4-4m10 0 4 4',
    'm14 2 3 2-8 12m-3-3 7 5-4 5-8-6zM17 16h5m-3-3v6',
    'm3 6 5-4 6 6-4 5-5-4m6 3 10 10m-8-5-4 5-3-3 4-5'
  ];
  const icon=i=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[i%paths.length]}"/></svg>`;
  const field=(name,label,type='text',value='')=>`<label>${esc(label)}</label><input name="${name}" type="${type}" value="${esc(value)}" required>`;
  const select=(name,label,options)=>`<label>${esc(label)}</label><select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('')}</select>`;
  function decorate(){
    document.querySelectorAll('.categorygrid .category').forEach((b,i)=>{b.querySelector('span').innerHTML=icon(i);});
    const navigationSymbols={overview:'◫',requests:'☷',properties:'⌂',tenants:'♙',profile:'⚙',report:'＋',publicCalendar:'▦',updates:'✉',quotes:'▤',accounts:'R',issues:'⚑',agencies:'⌖',websiteIssues:'⚑',calendar:'▦',monday:'R',regions:'♙'};
    document.querySelectorAll('#nav .nav-icon,#phoneNav button>span').forEach(n=>{
      n.textContent=(navigationSymbols[n.closest('[data-view]')?.dataset.view] || '·')+'\uFE0E';
    });
  }
  async function stages({api,app,showDetail,toast,context}){
    try{
      const d=await api('workflow/stages/');if(!app.isConnected || document.querySelector('[data-view=overview].active')===null)return;
      app.querySelector('#workflowStages')?.remove();app.querySelector('.stats')?.remove();app.querySelector('.heading')?.remove();
      if(['pm','admin'].includes(context?.user.role))app.querySelector('#rows')?.closest('.panel')?.remove();
      (app.querySelector('#attention') || app).insertAdjacentHTML(app.querySelector('#attention')?'afterend':'afterbegin',`<section class="workflow-overview${context?.user.role==='superadmin'?' ops-overview':''}" id="workflowStages">${context?.user.role==='superadmin'?'<div class="heading"><div><span class="eyebrow">SEVLINK OPERATIONS</span><h1>Your maintenance control room.</h1><p>Every request has a place. Every job has a clear next action.</p></div></div>':'<span class="eyebrow">MAINTENANCE OVERVIEW</span><h2>Maintenance Overview</h2>'}${d.summary?`<div class="stats">${d.summary.map(s=>`<div class="stat"><label>${esc(s.label)}</label><strong>${s.count}</strong><small>Saved maintenance records</small></div>`).join('')}</div>`:''}<div class="${d.stages.length===8?'stage-grid pm-stage-grid':'ops-pods'}">${d.stages.map((s,i)=>d.stages.length===8?`<button class="stage-card" data-stage="${s.key}"><span class="stage-icon">${icon(i)}</span><strong>${s.count}</strong><b>${esc(s.label)}</b><small>View jobs →</small></button>`:`<button class="ops-pod stage-card" data-stage="${s.key}"><span>${esc(s.label)}</span><b>${s.count}</b><small>View jobs →</small></button>`).join('')}</div><div id="stageJobs"></div>${d.upcoming.length?`<section class="panel"><h2>Upcoming attendance</h2>${d.upcoming.map(a=>`<article class="workflow-job-row" data-upcoming="${a.id}" role="button" tabindex="0" aria-label="Open job"><div><strong>${esc(a.property)}</strong><p>${esc(a.reference)} · ${esc(a.date)} · ${esc(a.window)}</p></div></article>`).join('')}</section>`:''}</section>`);
      app.querySelectorAll('[data-upcoming]').forEach(b=>b.onclick=async()=>{try{showDetail(await api(`requests/${b.dataset.upcoming}/`));}catch(e){toast(e.message);}});
      app.querySelectorAll('[data-stage]').forEach(b=>b.onclick=async event=>{
        try{const r=await api('workflow/stages/?stage='+b.dataset.stage);app.querySelectorAll('[data-stage]').forEach(c=>{c.classList.toggle('selected',c===b);c.setAttribute('aria-pressed',String(c===b));});const panel=app.querySelector('#stageJobs');if(!panel)return;
          panel.innerHTML=`<section class="panel"><h2>${esc(d.stages.find(s=>s.key===b.dataset.stage).label)}</h2><div class="cards">${r.results.map(j=>`<article class="card job-card" data-stage-job="${j.id}" role="button" tabindex="0" aria-label="Open job"><div class="toolbar"><span class="eyebrow">${esc(j.reference)}</span><span class="badge">${esc(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[j.urgency]||j.status)}</span>${j.safety_concern?'<span class="badge Urgent">Safety concern flagged</span>':''}</div><h2>${esc(j.property)}</h2><p><b>${esc(j.title)}</b><br>${esc(j.property_name||'')}<br>${esc(j.agency||'')}</p>${b.dataset.stage==='attention'&&j.attention_actions?.length?`<div class="notice job-attention-reasons"><h3>Action required</h3><ul>${j.attention_actions.map(a=>`<li><strong>${esc(a.action)}</strong>${Number(a.amount)>0?` · R ${esc(Number(a.amount).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2}))}`:''}${a.due_date?` · Due ${esc(a.due_date)}`:''}${a.appointment_date?` · Appointment ${esc(new Date(a.appointment_date).toLocaleString('en-ZA',{timeZone:'Africa/Johannesburg'}))}`:''}</li>`).join('')}</ul></div>`:''}</article>`).join('')||'<p>No jobs in this stage.</p>'}</div></section>`;
          panel.querySelectorAll('[data-stage-job]').forEach(c=>c.onclick=async()=>{try{showDetail(await api(`requests/${c.dataset.stageJob}/`));}catch(e){toast(e.message);}});
          if(event?.isTrusted)panel.scrollIntoView({block:'nearest',behavior:'smooth'});
        }catch(e){toast(e.message);}
      });
      if(context?.user.role==='superadmin'){app.querySelectorAll(':scope > .panel').forEach(p=>p.remove());app.querySelector('[data-stage=new]')?.click();}
    }catch(e){toast(e.message);}
  }
  let inboxGeneration=0;
  async function inbox({api,app,showDetail,toast}){
    const generation=++inboxGeneration;
    try{const d=await api('workflow/notifications/');if(generation!==inboxGeneration || !document.querySelector('[data-view=updates].active'))return;app.innerHTML=`<div class="heading"><div><span class="eyebrow">SAVED JOB UPDATES</span><h1>Updates & Notifications</h1><p>${d.unread} unread</p></div></div>${d.results.map(n=>`<article class="panel"><h2>${esc(n.label)}</h2><p>${esc(n.reference)} · ${esc(n.property)} · ${esc(new Date(n.at).toLocaleString('en-ZA'))}</p><button class="primary" data-notice="${n.id}" data-notice-job="${n.job}">Open job</button> <button class="secondary" data-notice-read="${n.id}" data-read="${!n.read}">${n.read?'Mark unread':'Mark read'}</button></article>`).join('')||'<section class="panel">No saved notifications yet.</section>'}`;
      app.querySelectorAll('[data-notice]').forEach(b=>b.onclick=async()=>{await api(`workflow/notifications/${b.dataset.notice}/`,{method:'POST',body:JSON.stringify({read:true})});showDetail(await api(`requests/${b.dataset.noticeJob}/`));});
      app.querySelectorAll('[data-notice-read]').forEach(b=>b.onclick=async()=>{await api(`workflow/notifications/${b.dataset.noticeRead}/`,{method:'POST',body:JSON.stringify({read:b.dataset.read==='true'})});inbox({api,app,showDetail,toast});});
    }catch(e){toast(e.message);}
  }
  function job(job,{api,context,modal,showDetail,toast}){
    const w=job.workflow;if(!w)return;
    const pm=['pm','admin'].includes(context.user.role),staff=context.user.role==='superadmin',tenant=context.user.role==='tenant';
    const previous=modal.dataset.job===job.id?modal.dataset.tab:'overview';modal.dataset.job=job.id;
    const children=[...modal.children],panels={};const names={overview:'Overview',comments:'Comments',attendance:'Attendance',...(!tenant?{quotes:'Quotes',invoices:'Invoices'}:{}),activity:'Timeline',reports:'Before & After Report',...(staff?{costs:'Private Costs'}:{})};
    const attention=job.tab_attention||{counts:{},unread:{}};
    const informational=new Set(['comments','reports','activity']);
    const nav=document.createElement('div');nav.className='tabs workflow-tabs';nav.setAttribute('role','tablist');modal.append(nav);
    const updateBadge=key=>{
      const b=nav.querySelector(`[data-tab="${key}"]`);if(!b)return;
      const count=attention.counts[key]||0;
      b.innerHTML=esc(names[key])+(count?` <span class="job-tab-count" aria-hidden="true">(${count})</span>`:'');
      b.setAttribute('aria-label',names[key]);
      b.setAttribute('aria-description',count+ (informational.has(key)?' unread updates':' items requiring attention'));
      b.title=names[key]+(count?` — ${count} ${informational.has(key)?'unread updates':'items requiring attention'}`:'');
    };
    for(const [key,label] of Object.entries(names)){
      const button=document.createElement('button');button.textContent=label;button.dataset.tab=key;button.setAttribute('role','tab');nav.append(button);
      button.id='job-tab-'+key;button.setAttribute('aria-controls','job-panel-'+key);const panel=document.createElement('section');panel.id='job-panel-'+key;panel.setAttribute('aria-labelledby',button.id);panel.dataset.tabPanel=key;panel.className='workflow-tab-panel';panel.setAttribute('role','tabpanel');panels[key]=panel;modal.append(panel);
      updateBadge(key);
    }
    const back=document.createElement('button');back.className='back-link';back.textContent='← Back to jobs';back.onclick=()=>modal.close();modal.prepend(back);
    const summary=document.createElement('section');summary.className='job-summary';modal.insertBefore(summary,nav);let inSummary=true;
    let group='overview';
    for(const element of children){
      if(element.matches('[data-close]'))continue;
      if(element.querySelector('h2')?.textContent.startsWith('Job attachments'))inSummary=false;
      if(inSummary){summary.append(element);continue;}
      if(element.tagName==='H2'){
        if(element.textContent==='Quotations')group='quotes';else if(element.textContent==='Invoices & payment status')group='invoices';else if(element.textContent.includes('Job conversation'))group='comments';
      }
      if(element.id==='quoteForm')group='quotes';
      if(element.id==='invoiceForm')group='invoices';
      if(element.classList.contains('tabs')){group='activity';element.remove();continue;}
      if(element.id==='jobcontent' || element.id==='statusForm')group='activity';
      let target=element.id==='attachmentForm'||element.querySelector('h2')?.textContent.startsWith('Job attachments')?'reports':group;
      const invoice=job.invoices.find(i=>i.id===element.dataset.recordId);
      if(invoice?.visibility==='internal' && staff)target='costs';
      panels[target].append(element);
    }
    if(staff){
      summary.insertAdjacentHTML('beforeend',`<details class="panel manual-move"><summary><strong>Move job manually</strong></summary><p>Sevlink override. Moving a stage does not create an appointment, payment or completion report. Existing invoice balances stay unchanged.</p><form id="manualJobMove"><label>Move to</label><select name="stage">${w.manual_move_options.map(s=>`<option value="${s.value}" ${s.value===w.stage?'selected':''}>${esc(s.label)}</option>`).join('')}</select><label>Reason for overriding the workflow</label><textarea name="reason" maxlength="1000" required></textarea><label><input type="checkbox" required> I confirm this manual override and its effect on the job status.</label><p role="alert" hidden></p><button type="submit" class="primary">Move job</button></form></details>`);
      const move=summary.querySelector('#manualJobMove');let moveKey=crypto.randomUUID(),priorMove='';
      move.onsubmit=async e=>{e.preventDefault();const b=move.querySelector('[type=submit]'),error=move.querySelector('[role=alert]');b.disabled=true;error.hidden=true;
        const values={...Object.fromEntries(new FormData(move)),version:job.version},signature=JSON.stringify(values);if(priorMove&&signature!==priorMove)moveKey=crypto.randomUUID();priorMove=signature;
        try{const saved=await api(`requests/${job.id}/manual-move/`,{method:'POST',body:signature,headers:{'Idempotency-Key':moveKey}});showDetail(saved);document.dispatchEvent(new CustomEvent('sevlink-job-moved'));toast('Job moved. The override reason is saved in its history.');}
        catch(e){error.textContent=e.message;error.hidden=false;}finally{if(b.isConnected)b.disabled=false;}
      };
    }
    if(w.manual_stage)summary.insertAdjacentHTML('beforeend','<div class="notice">Sevlink has updated the job stage manually. Confirmed appointments and recorded payments are shown separately in their tabs.</div>');
    const nextSteps={new:pm?'Review and route this maintenance request.':'The property manager is reviewing this request.',quoting:'Sevlink is preparing the quotation.',declined:'The PM declined the quotation. Review the decision in Quotes.',approval:staff?'Waiting PM approval':tenant?'Your property manager is reviewing the proposed work.':'Review the quotation and record your decision.',deposit:tenant?'Sevlink is preparing attendance arrangements.':'Awaiting the required confirmed payment and Sevlink verification.',ready:'Please confirm attendance date.',booked:'Review the confirmed attendance window and access arrangements.',underway:'Follow the work and share permitted progress updates.',invoice:'Completion documentation and the final invoice are being prepared.',payment:tenant?'The completed work is being finalised.':'Review the final invoice and outstanding payment.',closed:'This job remains available in the authorised history.'};
    summary.insertAdjacentHTML('beforeend',`<div class="professional-next-step"><span class="eyebrow">NEXT STEP</span>${staff&&w.stage==='approval'&&job.status!=='cancelled'?'<h2 style="font-size:26px;line-height:1.25;margin:12px 0 0">Waiting PM approval</h2>':'<p>'+esc(job.status==='cancelled'?'This job is cancelled. Its records remain available.':(!tenant&&w.stage==='deposit'&&w.deposit?.blockers?.length?w.deposit.blockers.join(' '):nextSteps[w.stage])||'Review the job record.')+'</p>'}</div>`);
    const reading=new Set();
    const acknowledge=async tab=>{
      const ids=attention.unread[tab]||[];if(!ids.length||reading.has(tab))return;
      reading.add(tab);
      try{
        const results=await Promise.allSettled(ids.map(id=>api(`workflow/notifications/${id}/`,{method:'POST',body:JSON.stringify({read:true})})));
        const failed=ids.filter((id,i)=>results[i].status==='rejected');attention.unread[tab]=failed;
        if(informational.has(tab))attention.counts[tab]=failed.length;
        else if(tab==='attendance' && !((pm&&w.attendance_ready&&!w.attendance.some(a=>['pending','confirmed'].includes(a.status)))||(staff&&w.attendance.some(a=>a.status==='pending'))))attention.counts[tab]=failed.length;
        updateBadge(tab);
        if(failed.length)toast('Some updates could not be marked read. Open this tab again to retry.');
      }finally{reading.delete(tab);}
    };
    const show=tab=>{modal.dataset.tab=tab;Object.entries(panels).forEach(([key,p])=>p.hidden=key!==tab);nav.querySelectorAll('button').forEach(b=>{b.classList.toggle('selected',b.dataset.tab===tab);b.setAttribute('aria-selected',String(b.dataset.tab===tab));});acknowledge(tab);};
    nav.querySelectorAll('button').forEach(b=>b.onclick=()=>show(b.dataset.tab));show(names[previous]?previous:'overview');
    const submit=(form,operation,transform=x=>x)=>{
      const key=crypto.randomUUID();form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('[type=submit]');if(b)b.disabled=true;
        try{const values=transform(Object.fromEntries(new FormData(form)));let body=JSON.stringify({version:job.version,...values});if(form.id==='workflowReview'){body=new FormData(form);body.set('version',job.version);if(!body.getAll('attachments').some(f=>f.size))body.delete('attachments');}await api(`requests/${job.id}/workflow/${operation}/`,{method:'POST',body,headers:{'Idempotency-Key':key}});showDetail(await api(`requests/${job.id}/`));toast('Saved to the job history.');}
        catch(e){let error=form.querySelector('[role=alert]');if(!error){error=document.createElement('p');error.setAttribute('role','alert');form.append(error);}error.textContent=e.message;error.hidden=false;}
        finally{if(b?.isConnected)b.disabled=false;}
      };
    };
    panels.overview.insertAdjacentHTML('afterbegin',`<section class="notice"><h2>${esc(w.job_type==='callout'?'Authorised Call-Out':w.job_type==='quoted'?'Quotation Required':'Awaiting PM review')}</h2>${w.spending_limit?`<p>Maximum authorised total: <strong>R ${esc(w.spending_limit)}</strong> · VAT-inclusive where applicable.</p>`:''}${tenant?'':`<p>${esc(w.access_responsibility==='pm'?'Property Manager Arranges Access':'Sevlink Arranges Access')}</p>`}${w.safety_concern?'<p><strong>Tenant has flagged a safety concern.</strong></p>':''}${w.compatibility?'<p>Historical workflow — review existing evidence before authorising further work.</p>':''}${w.closed_at?`<p>${w.manual_stage?'Closed manually by Sevlink. Invoice balances remain as recorded.':'Closed after final agency payment. All job history is retained.'}</p>`:''}${w.parent_request?'<p>Separately authorised additional work linked to the original call-out.</p>':''}</section>`);
    if(pm && job.status==='awaiting_review' && !w.authorised_at && !job.quotations.some(q=>q.status==='approved')){
      panels.overview.insertAdjacentHTML('beforeend',`<form id="workflowReview" class="panel"><h2>Send request to Sevlink</h2>${select('job_type','Job type',[['quoted','Quotation Required'],['callout','Call-Out']])}${select('urgency','Official urgency',[['normal','Normal'],['high','High'],['urgent','Urgent']])}${select('access_responsibility','Access responsibility',[['sevlink','Sevlink Arranges Access'],['pm','Property Manager Arranges Access']])}<div class="callout-limit" style="display:none"><label>Maximum authorised call-out total in ZAR (VAT-inclusive)</label><input name="limit" type="number" min="0.01" step="0.01"></div><label>Access information / further details</label><textarea name="access_information" maxlength="2500">${esc(w.access_information)}</textarea><label>Reason for review or change</label><textarea name="reason" maxlength="2500"></textarea><div class="notice">${job.attachments.filter(f=>f.purpose==='general').length?`${job.attachments.filter(f=>f.purpose==='general').length} request photos/documents are already attached and will be included automatically when you send this repair to Sevlink.`:'The tenant has not attached photos. You can add photos below before sending this repair to Sevlink.'}</div><label>Add repair photos (optional)</label><input name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><small>Choose photos together or add more selections. Up to 5 MB each and 25 MB total for this repair.</small><button type="submit" class="primary">Send to Sevlink</button></form>`);
      const reviewForm=panels.overview.querySelector('form');if(w.job_type!=='unclassified')reviewForm.elements.job_type.value=w.job_type;reviewForm.elements.urgency.value=job.urgency==='high'?'high':job.urgency==='urgent'?'urgent':'normal';reviewForm.elements.access_responsibility.value=w.access_responsibility;
      const toggleLimit=()=>{const active=reviewForm.elements.job_type.value==='callout';reviewForm.querySelector('.callout-limit').style.display=active?'':'none';reviewForm.elements.limit.disabled=!active;reviewForm.elements.limit.required=active;};reviewForm.elements.job_type.addEventListener('change',toggleLimit);toggleLimit();
      photoPicker(reviewForm.querySelector('[name=attachments]'),job.attachments.filter(f=>f.purpose==='general').reduce((n,f)=>n+f.size,0));
      submit(reviewForm,'review');
    }
    if(staff && w.job_type==='callout' && !w.closed_at){
      panels.overview.insertAdjacentHTML('beforeend',`<form id="extraWork" class="panel"><h2>Request additional spending authorisation</h2>${field('limit','New maximum total (ZAR)','number')}<label>Issue and reason · supporting photos can be added under Reports & Photos</label><textarea name="reason" required maxlength="2500"></textarea><button type="submit" class="primary">Request PM authorisation</button></form>`);
      submit(panels.overview.querySelector('#extraWork'),'additional-request');
    }
    for(const a of w.additional){
      panels.overview.insertAdjacentHTML('beforeend',`<section class="panel"><h2>Additional spending: R ${esc(a.amount)}</h2><p>${esc(a.reason)} · ${esc(a.status)}</p>${a.status==='pending'&&pm?`<form data-extra="${a.id}">${select('decision','Decision',[['approved','Approve higher total limit'],['declined','Decline expenditure'],['quotation','Request formal quotation as a separate job']])}<button type="submit" class="primary">Record decision</button></form>`:''}</section>`);
      const form=panels.overview.querySelector(`[data-extra="${a.id}"]`);if(form)submit(form,'additional-decision',v=>({...v,additional:a.id}));
    }
    panels.attendance.innerHTML=['completed','closed','cancelled'].includes(job.status)?'<div class="notice"><h2>Attendance history</h2><p>This job is '+(job.status==='cancelled'?'cancelled':'complete')+'. Previous attendance arrangements remain available below.</p></div>':w.attendance_ready?'<div class="notice"><h2>Please confirm attendance date</h2><p>This job is ready for attendance arrangements.</p></div>':'<div class="notice"><h2>Attendance arrangements are locked</h2><p>Complete the required work authorisation before arranging attendance.</p></div>';
    if(staff && w.attendance_ready && !['completed','closed','cancelled'].includes(job.status) && !w.attendance.some(a=>['pending','confirmed'].includes(a.status))){
      panels.attendance.innerHTML='<div class="notice"><h2>Awaiting PM attendance request</h2><p>The deposit is verified and attendance is unlocked. The property manager can now send a preferred date and arrival window, or request a call. Return here to review and confirm the appointment once their request arrives.</p></div>';
    }
    if(!tenant && !w.attendance_ready && w.deposit?.blockers?.length){
      panels.attendance.innerHTML=`<div class="notice"><h2>Attendance arrangements are locked</h2><p>${esc(w.deposit.blockers.join(' '))}</p><button class="secondary" type="button" id="attendanceDeposit">Review deposit</button></div>`;
      panels.attendance.querySelector('#attendanceDeposit').onclick=()=>show('invoices');
    }
    if(pm && w.attendance_ready && !w.attendance.some(a=>a.status==='pending')){
      panels.attendance.insertAdjacentHTML('beforeend',`<form id="attendanceRequest" class="panel">${select('preference','Attendance options',[['date','Select Preferred Date'],['call','Request a Call']])}${field('date','Preferred date','date')}${select('window','Subcontractor arrival window',w.arrival_windows.map(v=>[v,v]))}<p>These are arrival windows, not the length of the job. A preferred date is not a confirmed booking.</p><button type="submit" class="primary">Send attendance request</button></form>`);
      const f=panels.attendance.querySelector('form');f.elements.preference.onchange=()=>{f.elements.date.required=f.elements.preference.value==='date';f.elements.date.disabled=f.elements.preference.value==='call';f.elements.window.disabled=f.elements.preference.value==='call';};submit(f,'attendance-request');
    }
    const attendanceDate=value=>value?new Date(value+'T12:00:00+02:00').toLocaleDateString('en-ZA',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Africa/Johannesburg'}):'Date to be arranged';
    for(const a of w.attendance){
      const confirmed=a.status==='confirmed',day=confirmed?a.agreed_date:a.requested_date,window=confirmed?a.agreed_window:a.requested_window;
      const status={pending:'Awaiting confirmation',confirmed:'Confirmed appointment',declined:'Alternative date needed',cancelled:'Cancelled appointment'}[a.status]||a.status;
      panels.attendance.insertAdjacentHTML('beforeend',`<section class="panel attendance-card"><div class="attendance-card-header"><span class="eyebrow">${confirmed?'CONFIRMED ATTENDANCE':'REQUESTED ATTENDANCE'}</span><span class="badge ${confirmed?'Completed':'Awaiting'}">${esc(status)}</span></div><h2 class="attendance-date">${esc(a.preference==='call'&&!day?'Call requested':attendanceDate(day))}</h2>${window?`<p class="attendance-window"><span>Arrival window</span><strong>${esc(window)}</strong><small>South African time · arrival window, not job duration</small></p>`:'<p class="attendance-window">The PM has requested a call to arrange a suitable date.</p>'}${confirmed&&a.requested_date&&a.requested_date!==a.agreed_date?`<p>Originally requested: ${esc(attendanceDate(a.requested_date))}</p>`:''}${staff&&w.attendance_ready&&a.status!=='cancelled'?`<div class="actions attendance-actions">${confirmed?`<button class="secondary" type="button" data-arrival-action="alternative" data-confirm-arrival="${a.id}">Reschedule</button>`:`<button class="primary" type="button" data-arrival-action="accept" data-confirm-arrival="${a.id}">Accept</button><button class="secondary" type="button" data-arrival-action="alternative" data-confirm-arrival="${a.id}">Decline</button>`}</div><div data-arrival-form="${a.id}"></div>`:''}</section>`);
      panels.attendance.querySelectorAll(`[data-confirm-arrival="${a.id}"]`).forEach(b=>b.onclick=async()=>{
        const container=panels.attendance.querySelector(`[data-arrival-form="${a.id}"]`),generation=crypto.randomUUID();container.dataset.generation=generation;container.innerHTML='<p role="status">Loading appointment options…</p>';
        try{const calendar=await api('operations/calendar/');if(container.dataset.generation!==generation)return;const alternative=b.dataset.arrivalAction==='alternative';
          const needsContact=alternative||a.preference==='call'||a.status!=='pending';
          container.innerHTML=`<form class="attendance-decision"><h3>${alternative?'Choose an alternative date':'Assign subcontractor and confirm attendance'}</h3><p>${alternative?'Enter the new date manually, agree it with the client, then assign the subcontractor and team.':'The preferred date is retained. Select the subcontractor and team before confirming the appointment.'}</p>${field('date',alternative?'Alternative attendance date':'Attendance date','date',alternative?'':a.agreed_date||a.requested_date||'')}${select('window','Arrival window',w.arrival_windows.map(v=>[v,v]))}${needsContact?'<label><input type="checkbox" name="client_confirmed" required> I have agreed this date with the client / tenant</label>'+select('contact_category','Who was contacted?',[['','Select contact'],['tenant','Tenant'],['pm','Property Manager'],['other','Other Authorised Contact']]):''}${select('subcontractor','Assign subcontractor',[['','Select subcontractor'],...calendar.suppliers.map(s=>[s.id,s.name])])}${select('team','Assign team',[['','Select team']])}${field('start','Private booking start time','time','09:00')}${field('end','Private booking end time','time','10:00')}${alternative||confirmed?'<label>Reason for alternative date</label><textarea name="reason" required maxlength="1000"></textarea>':''}<details><summary>Overlap exception (Super Admin only)</summary><label>Authorised overlap reason</label><textarea name="override_reason"></textarea></details><div class="actions"><button type="submit" class="primary">${alternative?'Confirm alternative appointment':'Assign subbie & confirm attendance'}</button></div><p role="alert" hidden></p></form>`;
          const f=container.querySelector('form'),key=crypto.randomUUID();
          if(!alternative&&a.preference==='date'&&a.status==='pending'){f.elements.date.readOnly=true;f.elements.window.disabled=true;}
          f.elements.window.value=a.agreed_window||a.requested_window||w.arrival_windows[0];
          const setTimes=()=>{const afternoon=f.elements.window.value.startsWith('12:');f.elements.start.value=afternoon?'12:00':'09:00';f.elements.end.value=afternoon?'13:00':'10:00';};setTimes();f.elements.window.onchange=setTimes;
          f.elements.subcontractor.required=true;f.elements.team.required=true;if(needsContact)f.elements.contact_category.required=true;
          f.elements.subcontractor.onchange=()=>{f.elements.team.innerHTML='<option value="">Select team</option>'+calendar.all_teams.filter(t=>t.subcontractor===f.elements.subcontractor.value).map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('');};
          f.onsubmit=async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(f)),button=f.querySelector('[type=submit]'),error=f.querySelector('[role=alert]');button.disabled=true;error.hidden=true;
            try{const old=a.appointment_id?{id:a.appointment_id}:calendar.appointments.find(p=>p.job===job.id);const body={version:job.version,attendance:a.id,date:v.date,window:f.elements.window.value,client_confirmed:f.elements.client_confirmed?.checked||false,contact_category:v.contact_category||'',subcontractor:v.subcontractor,team:v.team,starts_at:v.date+'T'+v.start+':00+02:00',ends_at:v.date+'T'+v.end+':00+02:00'};if(old)body.appointment=old.id;if(v.reason)body.reason=v.reason;if(v.override_reason)body.override_reason=v.override_reason;
              await api(`requests/${job.id}/workflow/confirm-attendance/`,{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(body)});showDetail(await api(`requests/${job.id}/`));
            }catch(e){error.hidden=false;error.textContent=e.message;error.scrollIntoView({block:'nearest'});}finally{if(button.isConnected)button.disabled=false;}
          };
          container.scrollIntoView({block:'nearest'});
        }catch(e){if(container.dataset.generation===generation)container.innerHTML=`<p role="alert">${esc(e.message)}</p>`;}
      });
    }
    if(staff && !['completed','closed','cancelled'].includes(job.status) && (w.job_type==='quoted'||w.compatibility) && job.quotations.some(q=>q.status==='approved')&&!w.attendance_ready){panels.invoices.insertAdjacentHTML('afterbegin','<form id="verifyDeposit" class="panel"><h2>Verify and allocate received deposit</h2><p>A Paid invoice confirms the receipt was recorded. Verify its allocation to this job to unlock attendance. No additional payment is recorded here.</p><label>Type VERIFY to confirm</label><input name="confirmation" required pattern="VERIFY"><button type="submit" class="primary">Verify deposit</button></form>');submit(panels.invoices.querySelector('#verifyDeposit'),'verify-deposit');}
    const evidence=(job.attachments||[]).filter(f=>['completion_before','completion_after'].includes(f.purpose));
    const photos=kind=>evidence.filter(f=>f.purpose===kind&&f.content_type.startsWith('image/')).map(f=>`<a href="${esc(f.download_url)}" download><img src="${esc(f.download_url)}" alt="${esc((kind==='completion_before'?'Before work: ':'After work: ')+f.filename)}" loading="lazy"><small>${esc(f.filename)}</small></a>`).join('')||'<p class="photo-placeholder">No photographs recorded.</p>';
    panels.reports.insertAdjacentHTML('afterbegin',`<article class="completion-report sevlink-document"><div class="document-header"><img src="sevlink-logo.png" alt="Sevlink"><div><span class="eyebrow">WORK COMPLETION REPORT</span><h2>${esc(job.reference)}</h2></div></div><div class="document-property"><h2>${esc(job.property.address)}</h2><p>${esc(job.title)}</p></div>${w.completion.length?w.completion.map(c=>`<section class="panel"><h3>Work carried out</h3><p class="report-summary">${esc(c.report)}</p><small>${esc(new Date(c.created_at).toLocaleString('en-ZA',{timeZone:'Africa/Johannesburg'}))}</small>${c.before_unavailable?`<p>Before photographs unavailable · audited exception: ${esc(c.exception_reason)}</p>`:''}</section>`).join(''):'<p>No accepted completion report has been recorded yet.</p>'}<div class="photo-pair"><section><h3>Before</h3>${photos('completion_before')}</section><section><h3>After</h3>${photos('completion_after')}</section></div></article>`);
    if(staff&&!w.closed_at){
      panels.reports.insertAdjacentHTML('beforeend',`<form id="completedReportUpload" class="panel"><h2>Upload the completed work report</h2><p>After the work is finished, upload both sets of photographs here. They are placed in the Before and After sections automatically.</p><label>Before-work photos (taken before the repair)</label><input name="before_photos" type="file" multiple accept="image/jpeg,image/png,image/webp"><label>After-work photos (taken after completion)</label><input name="after_photos" type="file" multiple accept="image/jpeg,image/png,image/webp"><small>Up to five photos in each selection, 5 MB each. Previously uploaded report photos are retained.</small>${job.allowed_statuses.some(s=>s.value==='completed')?'<label><input name="mark_completed" type="checkbox"> All report photos are included — mark the work Completed when saving</label>':''}<label>Work completed / report summary</label><textarea name="report" required maxlength="5000" rows="5"></textarea><label><input name="before_unavailable" type="checkbox"> Before-work photos are unavailable</label><label>Reason if before photos are unavailable</label><textarea name="exception_reason" maxlength="1000"></textarea><div class="actions"><button type="submit" class="primary">Upload photos & save completed report</button></div><p role="alert" hidden></p><p role="status">The completed report and final invoice are queued together for the PM when both are ready and the job is marked Completed.</p></form><div id="completionPackageStatus" class="notice" role="status"></div>`);
      const form=panels.reports.querySelector('#completedReportUpload'),key=crypto.randomUUID();form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('[type=submit]'),error=form.querySelector('[role=alert]');button.disabled=true;error.hidden=true;
        try{const body=new FormData(form);body.set('version',job.version);body.set('before_unavailable',String(form.elements.before_unavailable.checked));body.set('mark_completed',String(form.elements.mark_completed?.checked||false));await api(`requests/${job.id}/completed-report/`,{method:'POST',body,headers:{'Idempotency-Key':key}});showDetail(await api(`requests/${job.id}/`));toast('Completed report saved.');}
        catch(e){error.hidden=false;error.textContent=e.message;error.scrollIntoView({block:'nearest'});}finally{if(button.isConnected)button.disabled=false;}
      };
      api(`requests/${job.id}/completion-package/`).then(d=>{const slot=panels.reports.querySelector('#completionPackageStatus');if(slot.isConnected)slot.innerHTML=d.queued?`<b>Report and final invoice: ${esc(d.state==='sent'?'accepted by email server':d.state==='blocked'?'delivery needs review':d.state==='failed'?'delivery failed':d.state==='preview'?'local preview ready — not sent':'queued together')}</b><p>Invoice ${esc(d.invoice_number)}</p>${d.live_enabled?'':'<p>Live email is disabled. No real email has been sent.</p>'}<a class="secondary" href="${esc(d.report_url)}" download>Download completed report PDF</a>`:'The combined PM email will be prepared when the completed report and final invoice are both saved. Live sending remains controlled by your email delivery settings.';}).catch(e=>{const slot=panels.reports.querySelector('#completionPackageStatus');if(slot?.isConnected)slot.textContent=e.message;});
    }
    if(!tenant && w.deposit && job.quotations.some(q=>q.status==='approved')){
      const d=w.deposit,format=value=>'R '+Number(value).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
      const state=Number(d.outstanding)>0?'Deposit still required: '+format(d.outstanding):d.ready?(w.attendance_ready?'Deposit received · ready to schedule':'Deposit verified'):d.verification_recorded?'Deposit verified · '+(d.blockers||[]).join(' '):'Payment recorded · verify the deposit below to unlock attendance';
      panels.invoices.insertAdjacentHTML('afterbegin',`<div class="notice" style="margin:18px 0"><b>Quoted work · 50% deposit</b><p>Approved quote total: ${esc(format(d.basis))}<br>Deposit required: ${esc(format(d.required))}<br>Recorded payments received: ${esc(format(d.received))}<br><b>${esc(state)}</b></p><p>Recorded receipts and deposit verification are separate. Scheduling unlocks after the required funds are received and their deposit allocation is verified.</p></div><div class="notice"><b>Full job balance</b><p>Full job: ${esc(format(d.basis))}<br>Recorded received: ${esc(format(d.received))}<br><b>Still to pay: ${esc(format(Math.max(0,Number(d.basis)-Number(d.received))))}</b></p><p>${job.invoices.filter(i=>i.visibility!=='internal'&&i.document_status==='active').length>1?'Payments stay against their original saved invoices. Existing invoice history is preserved.':'Deposit and final payments stay on the original invoice number.'}</p></div>`);
    }
    const privateForm=panels.invoices?.querySelector('#invoiceForm');if(privateForm){
      const visibility=privateForm.elements.visibility;visibility.value='shared';visibility.innerHTML='<option value="shared">Agency-visible Sevlink invoice</option>';
    }
    if(staff){
      const slot=document.createElement('section');slot.className='panel';panels.costs.append(slot);
      api(`operations/requests/${job.id}/assignments/`).then(d=>{
        if(!slot.isConnected)return;
        const assigned=[...new Map(d.history.map(a=>[a.subcontractor,a])).values()];
        slot.innerHTML=assigned.length?`<form id="privateCostUpload"><h2>Upload assigned subcontractor invoice</h2>${select('subcontractor','Assigned subcontractor',assigned.map(a=>[a.subcontractor,a.name]))}${field('number','Reference printed on supplier PDF')}${field('amount','Invoice amount (ZAR)','number')}<label>Private supplier invoice PDF</label><input type="file" name="attachments" required accept="application/pdf"><p>Payment is tracked manually. Due date is the next Monday after upload.</p><button type="submit" class="primary">Upload private supplier invoice</button></form>`:'<p>No assigned subcontractor invoice can be uploaded until an authorised assignment exists.</p>';
        const f=slot.querySelector('form');if(f){const key=crypto.randomUUID();f.onsubmit=async e=>{e.preventDefault();try{const body=new FormData(f);body.set('visibility','internal');body.set('purpose','supplier');body.set('due_date',new Date().toLocaleDateString('en-CA',{timeZone:'Africa/Johannesburg'}));await api(`requests/${job.id}/invoices/`,{method:'POST',body,headers:{'Idempotency-Key':key}});showDetail(await api(`requests/${job.id}/`));}catch(e){toast(e.message);}};}
      }).catch(e=>toast(e.message));
    }
    if(!staff && !w.compatibility)panels.activity.querySelector('#statusForm')?.remove();
    panels.activity.insertAdjacentHTML('beforeend',w.history.map(h=>`<article class="activity"><strong>${esc(h.action)}</strong><small>${esc(h.actor)} · ${esc(new Date(h.at).toLocaleString('en-ZA'))}</small></article>`).join(''));
  }
  async function agencies({api,app,showDetail,toast}) {
    try {const d=await api('workflow/agencies/');if(!document.querySelector('[data-view=agencies].active'))return;app.innerHTML='<div class="heading"><div><span class="eyebrow">SEVLINK OPERATIONS</span><h1>Agencies</h1><p>Registered agencies, authorised portfolios and saved maintenance jobs.</p></div></div>'+d.agencies.map(a=>`<section class="panel"><div class="toolbar"><h2 style="flex:1">${esc(a.name)}</h2><button class="secondary" data-remove-kind="agency" data-remove-id="${a.id}">Remove agency</button></div>${a.properties.map(p=>`<details class="panel" open><summary><strong>${esc(p.address)}</strong> · ${esc(p.manager||'Agency managed')}</summary><button class="secondary" data-remove-kind="property" data-remove-id="${p.id}">Remove property</button><h3>Tenants</h3>${p.tenants.map(t=>`<div class="toolbar"><span style="flex:1">${esc(t.name)}</span><button class="secondary" data-remove-kind="tenant" data-remove-id="${t.id}">Remove tenant</button></div>`).join('')||'<p>No active tenancy</p>'}${p.jobs.map(j=>`<article class="workflow-job-row"><span>${esc(j.reference)} · ${esc(j.title)} · ${esc(j.status)}</span><button class="secondary" data-agency-job="${j.id}">Open job</button></article>`).join('')}</details>`).join('')||'<p>No registered properties.</p>'}</section>`).join('')+`<section id="removalReview" class="panel" hidden></section>${d.pending_cleanups.length?`<section class="panel"><h2>Private file cleanup pending</h2>${d.pending_cleanups.map(r=>`<p>${esc(r.kind)} removal · ${r.files} files <button class="secondary" data-retry-cleanup="${r.id}">Retry cleanup</button></p>`).join('')}</section>`:''}`;app.querySelectorAll('[data-retry-cleanup]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const r=await api(`admin/removals/${b.dataset.retryCleanup}/cleanup/`,{method:'POST',body:'{}'});await agencies({api,app,showDetail,toast});toast(r.cleanup_pending?'Some files still need cleanup.':'Private files removed.');}catch(e){toast(e.message);b.disabled=false;}});app.querySelectorAll('[data-remove-kind]').forEach(b=>b.onclick=async()=>{
        try{const path=`admin/remove/${b.dataset.removeKind}/${b.dataset.removeId}/`,d=await api(path),panel=app.querySelector('#removalReview');panel.hidden=false;
          panel.innerHTML=`<h2>${d.keeps_jobs?'Remove tenant account':'Permanently remove '+esc(d.kind)}</h2><p><strong>${esc(d.name)}</strong></p><p>${esc(d.note)}</p><ul>${Object.entries(d.counts).filter(([,v])=>v).map(([k,v])=>`<li>${esc(k.replace('portal.','').replaceAll('_',' '))}: ${v}</li>`).join('')}</ul><form id="confirmRemoval"><label>Type REMOVE to confirm</label><input name="confirmation" required pattern="REMOVE"><p role="alert" hidden></p><button class="primary" type="submit">${d.keeps_jobs?'Remove tenant account':'Permanently remove'}</button> <button type="button" id="cancelRemoval" class="secondary">Cancel</button></form>`;
          panel.scrollIntoView({block:'center'});panel.querySelector('#cancelRemoval').onclick=()=>{panel.hidden=true;panel.innerHTML='';};
          panel.querySelector('form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]'),error=e.target.querySelector('[role=alert]');button.disabled=true;
            try{const result=await api(path,{method:'POST',body:JSON.stringify({token:d.token,confirmation:new FormData(e.target).get('confirmation')})});await agencies({api,app,showDetail,toast});toast(d.keeps_jobs?'Tenant account removed. Jobs and invoices are retained.':'Selected records removed.');
              if(result.cleanup_pending){const target=app.querySelector('#removalReview');target.hidden=false;target.innerHTML='<h2>Private file cleanup pending</h2><p>The records were removed, but some files could not be deleted yet.</p><button class="primary" id="retryRemovalCleanup">Retry file cleanup</button>';target.querySelector('button').onclick=async()=>{try{const r=await api(`admin/removals/${result.receipt}/cleanup/`,{method:'POST',body:'{}'});if(!r.cleanup_pending){target.hidden=true;toast('Private files removed.');}else toast('File cleanup is still pending.');}catch(e){toast(e.message);}};}
            }catch(e){error.hidden=false;error.textContent=e.message;button.disabled=false;}
          };
        }catch(e){toast(e.message);}
      });app.querySelectorAll('[data-agency-job]').forEach(b=>b.onclick=async()=>{try{showDetail(await api(`requests/${b.dataset.agencyJob}/`));}catch(e){toast(e.message);}});}catch(e){toast(e.message);}
  }
  return {icon,decorate,stages,inbox,job,agencies,photoPicker};
})();
