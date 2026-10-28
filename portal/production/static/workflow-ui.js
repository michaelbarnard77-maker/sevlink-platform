/* Real Django workflow presentation; no localStorage, sample records or operational simulation. */
window.SevlinkWorkflowUI = (() => {
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
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
      (app.querySelector('#attention') || app).insertAdjacentHTML(app.querySelector('#attention')?'afterend':'afterbegin',`<section class="workflow-overview${context?.user.role==='superadmin'?' ops-overview':''}" id="workflowStages">${context?.user.role==='superadmin'?'<div class="heading"><div><span class="eyebrow">SEVLINK OPERATIONS</span><h1>Your maintenance control room.</h1><p>Every request has a place. Every job has a clear next action.</p></div></div>':'<span class="eyebrow">MAINTENANCE OVERVIEW</span><h2>Maintenance Overview</h2>'}${d.summary?`<div class="stats">${d.summary.map(s=>`<div class="stat"><label>${esc(s.label)}</label><strong>${s.count}</strong><small>Saved maintenance records</small></div>`).join('')}</div>`:''}<div class="${d.stages.length===8?'stage-grid pm-stage-grid':'ops-pods'}">${d.stages.map((s,i)=>d.stages.length===8?`<button class="stage-card" data-stage="${s.key}"><span class="stage-icon">${icon(i)}</span><strong>${s.count}</strong><b>${esc(s.label)}</b><small>View jobs →</small></button>`:`<button class="ops-pod stage-card" data-stage="${s.key}"><span>${esc(s.label)}</span><b>${s.count}</b><small>View jobs →</small></button>`).join('')}</div><div id="stageJobs"></div>${d.upcoming.length?`<section class="panel"><h2>Upcoming attendance</h2>${d.upcoming.map(a=>`<article class="workflow-job-row"><div><strong>${esc(a.property)}</strong><p>${esc(a.reference)} · ${esc(a.date)} · ${esc(a.window)}</p></div><button class="secondary" data-upcoming="${a.id}">Open job</button></article>`).join('')}</section>`:''}</section>`);
      app.querySelectorAll('[data-upcoming]').forEach(b=>b.onclick=async()=>{try{showDetail(await api(`requests/${b.dataset.upcoming}/`));}catch(e){toast(e.message);}});
      app.querySelectorAll('[data-stage]').forEach(b=>b.onclick=async event=>{
        try{const r=await api('workflow/stages/?stage='+b.dataset.stage);app.querySelectorAll('[data-stage]').forEach(c=>{c.classList.toggle('selected',c===b);c.setAttribute('aria-pressed',String(c===b));});const panel=app.querySelector('#stageJobs');if(!panel)return;
          panel.innerHTML=`<section class="panel"><h2>${esc(d.stages.find(s=>s.key===b.dataset.stage).label)}</h2><div class="cards">${r.results.map(j=>`<article class="card job-card"><div class="toolbar"><span class="eyebrow">${esc(j.reference)}</span><span class="badge">${esc(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[j.urgency]||j.status)}</span>${j.safety_concern?'<span class="badge Urgent">Safety concern flagged</span>':''}</div><h2>${esc(j.property)}</h2><p><b>${esc(j.title)}</b><br>${esc(j.property_name||'')}<br>${esc(j.agency||'')}</p>${b.dataset.stage==='attention'&&j.attention_actions?.length?`<div class="notice job-attention-reasons"><h3>Action required</h3><ul>${j.attention_actions.map(a=>`<li><strong>${esc(a.action)}</strong>${Number(a.amount)>0?` · R ${esc(Number(a.amount).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2}))}`:''}${a.due_date?` · Due ${esc(a.due_date)}`:''}${a.appointment_date?` · Appointment ${esc(new Date(a.appointment_date).toLocaleString('en-ZA',{timeZone:'Africa/Johannesburg'}))}`:''}</li>`).join('')}</ul></div>`:''}<button class="secondary" data-stage-job="${j.id}">Open job</button></article>`).join('')||'<p>No jobs in this stage.</p>'}</div></section>`;
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
    const nextSteps={new:pm?'Review and route this maintenance request.':'The property manager is reviewing this request.',quoting:'Sevlink is preparing the quotation.',approval:tenant?'Your property manager is reviewing the proposed work.':'Review the quotation and record your decision.',deposit:tenant?'Sevlink is preparing attendance arrangements.':'Awaiting the required confirmed payment and Sevlink verification.',ready:'Please confirm attendance date.',booked:'Review the confirmed attendance window and access arrangements.',underway:'Follow the work and share permitted progress updates.',invoice:'Completion documentation and the final invoice are being prepared.',payment:tenant?'The completed work is being finalised.':'Review the final invoice and outstanding payment.',closed:'This job remains available in the authorised history.'};
    summary.insertAdjacentHTML('beforeend',`<div class="professional-next-step"><span class="eyebrow">NEXT STEP</span><p>${esc(job.status==='cancelled'?'This job is cancelled. Its records remain available.':nextSteps[w.stage]||'Review the job record.')}</p></div>`);
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
        try{const values=transform(Object.fromEntries(new FormData(form)));await api(`requests/${job.id}/workflow/${operation}/`,{method:'POST',body:JSON.stringify({version:job.version,...values}),headers:{'Idempotency-Key':key}});showDetail(await api(`requests/${job.id}/`));toast('Saved to the job history.');}
        catch(e){let error=form.querySelector('[role=alert]');if(!error){error=document.createElement('p');error.setAttribute('role','alert');form.append(error);}error.textContent=e.message;}
        finally{if(b?.isConnected)b.disabled=false;}
      };
    };
    panels.overview.insertAdjacentHTML('afterbegin',`<section class="notice"><h2>${esc(w.job_type==='callout'?'Authorised Call-Out':w.job_type==='quoted'?'Quotation Required':'Awaiting PM review')}</h2>${w.spending_limit?`<p>Maximum authorised total: <strong>R ${esc(w.spending_limit)}</strong> · VAT-inclusive where applicable.</p>`:''}<p>${esc(w.access_responsibility==='pm'?'Property Manager Arranges Access':'Sevlink Arranges Access')}</p>${w.safety_concern?'<p><strong>Tenant has flagged a safety concern.</strong></p>':''}${w.compatibility?'<p>Historical workflow — review existing evidence before authorising further work.</p>':''}${w.closed_at?'<p>Closed after final agency payment. All job history is retained.</p>':''}${w.parent_request?'<p>Separately authorised additional work linked to the original call-out.</p>':''}</section>`);
    if(pm && job.status==='awaiting_review' && !w.authorised_at && !job.quotations.some(q=>q.status==='approved')){
      panels.overview.insertAdjacentHTML('beforeend',`<form id="workflowReview" class="panel"><h2>Send request to Sevlink</h2>${select('job_type','Job type',[['quoted','Quotation Required'],['callout','Call-Out']])}${select('urgency','Official urgency',[['normal','Normal'],['high','High'],['urgent','Urgent']])}${select('access_responsibility','Access responsibility',[['sevlink','Sevlink Arranges Access'],['pm','Property Manager Arranges Access']])}<label>Maximum authorised call-out total in ZAR (VAT-inclusive)</label><input name="limit" type="number" min="0.01" step="0.01"><label>Access information / further details</label><textarea name="access_information" maxlength="2500">${esc(w.access_information)}</textarea><label>Reason for review or change</label><textarea name="reason" maxlength="2500"></textarea><button type="submit" class="primary">Send to Sevlink</button></form>`);
      const reviewForm=panels.overview.querySelector('form');if(w.job_type!=='unclassified')reviewForm.elements.job_type.value=w.job_type;reviewForm.elements.urgency.value=job.urgency==='high'?'high':job.urgency==='urgent'?'urgent':'normal';reviewForm.elements.access_responsibility.value=w.access_responsibility;
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
    if(pm && w.attendance_ready && !w.attendance.some(a=>a.status==='pending')){
      panels.attendance.insertAdjacentHTML('beforeend',`<form id="attendanceRequest" class="panel">${select('preference','Attendance options',[['date','Select Preferred Date'],['call','Request a Call']])}${field('date','Preferred date','date')}${select('window','Subcontractor arrival window',w.arrival_windows.map(v=>[v,v]))}<p>These are arrival windows, not the length of the job. A preferred date is not a confirmed booking.</p><button type="submit" class="primary">Send attendance request</button></form>`);
      const f=panels.attendance.querySelector('form');f.elements.preference.onchange=()=>{f.elements.date.required=f.elements.preference.value==='date';f.elements.date.disabled=f.elements.preference.value==='call';f.elements.window.disabled=f.elements.preference.value==='call';};submit(f,'attendance-request');
    }
    for(const a of w.attendance){
      panels.attendance.insertAdjacentHTML('beforeend',`<section class="panel"><h2>${esc(a.status)}</h2><p>Requested: ${esc(a.requested_date||'Request a Call')} ${esc(a.requested_window)}</p>${a.agreed_date?`<p>Confirmed: ${esc(a.agreed_date)} · ${esc(a.agreed_window)}</p>`:''}${staff&&w.attendance_ready&&a.status!=='cancelled'?`<button class="secondary" data-confirm-arrival="${a.id}">${a.status==='confirmed'?'Reschedule confirmed attendance':'Accept / Decline / arrange attendance'}</button><div data-arrival-form="${a.id}"></div>`:''}</section>`);
      const b=panels.attendance.querySelector(`[data-confirm-arrival="${a.id}"]`);if(b)b.onclick=async()=>{
        try{const calendar=await api('operations/calendar/');const container=panels.attendance.querySelector(`[data-arrival-form="${a.id}"]`);
          container.innerHTML=`<form>${select('action','Operations decision',[['confirm','Confirm booking'],['decline','Decline / arrange alternative']])}${field('date','Agreed date','date',a.agreed_date||a.requested_date||'')}${select('window','Public arrival window',w.arrival_windows.map(v=>[v,v]))}<label><input type="checkbox" name="client_confirmed"> Confirmed date with client/tenant</label>${select('contact_category','Who was contacted?',[['','Select when confirming an alternative'],['tenant','Tenant'],['pm','Property Manager'],['other','Other Authorised Contact']])}${select('subcontractor','Private subcontractor',calendar.suppliers.map(s=>[s.id,s.name]))}${select('team','Private team',calendar.all_teams.map(t=>[t.id,t.name+' · '+(calendar.suppliers.find(s=>s.id===t.subcontractor)?.name||'')]))}${field('start','Actual private start time','time','09:00')}${field('end','Actual private end time','time','10:00')}<label>Rescheduling / decline reason</label><textarea name="reason"></textarea><label>Super Admin overlap exception reason (only when required)</label><textarea name="override_reason"></textarea><button type="submit" class="primary">Save attendance decision</button><p role="alert"></p></form>`;
          const f=container.querySelector('form'),key=crypto.randomUUID();f.onsubmit=async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(f));try{
            if(v.action==='decline')await api(`requests/${job.id}/workflow/attendance-decline/`,{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify({version:job.version,additional:a.id,reason:v.reason})});
            else {const old=a.appointment_id?{id:a.appointment_id}:calendar.appointments.find(p=>p.job===job.id);const body={version:job.version,attendance:a.id,date:v.date,window:v.window,client_confirmed:f.elements.client_confirmed.checked,contact_category:v.contact_category,subcontractor:v.subcontractor,team:v.team,starts_at:v.date+'T'+v.start+':00+02:00',ends_at:v.date+'T'+v.end+':00+02:00'};if(old){body.appointment=old.id;body.reason=v.reason;}if(v.override_reason)body.override_reason=v.override_reason;await api(`requests/${job.id}/workflow/confirm-attendance/`,{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(body)});}
            showDetail(await api(`requests/${job.id}/`));
          }catch(e){f.querySelector('[role=alert]').textContent=e.message;}};
        }catch(e){toast(e.message);}
      };
    }
    if(staff && !['completed','closed','cancelled'].includes(job.status) && (w.job_type==='quoted'||w.compatibility) && job.quotations.some(q=>q.status==='approved')&&!w.attendance_ready){panels.invoices.insertAdjacentHTML('beforeend','<form id="verifyDeposit" class="panel"><h2>Verify and allocate received deposit</h2><p>Record the actual receipt above first. Verification requires sufficient confirmed funds.</p><label>Type VERIFY to confirm</label><input name="confirmation" required pattern="VERIFY"><button type="submit" class="primary">Verify deposit</button></form>');submit(panels.invoices.querySelector('#verifyDeposit'),'verify-deposit');}
    const evidence=(job.attachments||[]).filter(f=>['completion_before','completion_after'].includes(f.purpose));
    const photos=kind=>evidence.filter(f=>f.purpose===kind&&f.content_type.startsWith('image/')).map(f=>`<a href="${esc(f.download_url)}" download><img src="${esc(f.download_url)}" alt="${esc((kind==='completion_before'?'Before work: ':'After work: ')+f.filename)}" loading="lazy"><small>${esc(f.filename)}</small></a>`).join('')||'<p class="photo-placeholder">No photographs recorded.</p>';
    panels.reports.insertAdjacentHTML('afterbegin',`<article class="completion-report sevlink-document"><div class="document-header"><img src="sevlink-logo.png" alt="Sevlink"><div><span class="eyebrow">WORK COMPLETION REPORT</span><h2>${esc(job.reference)}</h2></div></div><div class="document-property"><h2>${esc(job.property.address)}</h2><p>${esc(job.title)}</p></div>${w.completion.length?w.completion.map(c=>`<section class="panel"><h3>Work carried out</h3><p class="report-summary">${esc(c.report)}</p><small>${esc(new Date(c.created_at).toLocaleString('en-ZA',{timeZone:'Africa/Johannesburg'}))}</small>${c.before_unavailable?`<p>Before photographs unavailable · audited exception: ${esc(c.exception_reason)}</p>`:''}</section>`).join(''):'<p>No accepted completion report has been recorded yet.</p>'}<div class="photo-pair"><section><h3>Before</h3>${photos('completion_before')}</section><section><h3>After</h3>${photos('completion_after')}</section></div></article>`);
    if(staff&&!w.closed_at){panels.reports.insertAdjacentHTML('beforeend',`<form id="completionUpload" class="panel">${select('kind','Document type',[['completion_before','Before-work photographs'],['completion_after','After-work photographs'],['completion_report','Completion report PDF']])}<input type="file" name="attachments" multiple required accept="image/jpeg,image/png,image/webp,application/pdf"><button type="submit" class="secondary">Upload completion evidence</button></form><form id="completionAccept" class="panel"><h2>Accept completion documentation</h2><label>Completion report</label><textarea name="report" required maxlength="5000"></textarea><label><input name="before_unavailable" type="checkbox"> I confirm that before-work photographs are unavailable for this job.</label><label>Reason if before photographs are unavailable</label><textarea name="exception_reason"></textarea><button type="submit" class="primary">Save completion documentation</button></form>`);
      const upload=panels.reports.querySelector('#completionUpload');upload.onsubmit=async e=>{e.preventDefault();try{await api(`requests/${job.id}/workflow/documents/`,{method:'POST',body:new FormData(upload)});showDetail(await api(`requests/${job.id}/`));}catch(e){toast(e.message);}};
      submit(panels.reports.querySelector('#completionAccept'),'completion',v=>({...v,before_unavailable:panels.reports.querySelector('[name=before_unavailable]').checked}));
    }
    if(!tenant && w.deposit && job.quotations.some(q=>q.status==='approved')){
      const d=w.deposit,format=value=>'R '+Number(value).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
      const state=Number(d.outstanding)>0?'Deposit still required: '+format(d.outstanding):d.ready?(w.attendance_ready?'Deposit received · ready to schedule':'Deposit verified'):'Deposit received · awaiting Sevlink verification';
      panels.invoices.insertAdjacentHTML('afterbegin',`<div class="notice" style="margin:18px 0"><b>Quoted work · 50% deposit</b><p>Approved quote total: ${esc(format(d.basis))}<br>Deposit required: ${esc(format(d.required))}<br>Verified payments received: ${esc(format(d.received))}<br><b>${esc(state)}</b></p><p>Only bank-verified payments count toward the deposit. Scheduling requires Sevlink verification.</p></div><div class="notice"><b>Full job balance</b><p>Full job: ${esc(format(d.basis))}<br>Verified received: ${esc(format(d.received))}<br><b>Still to pay: ${esc(format(Math.max(0,Number(d.basis)-Number(d.received))))}</b></p><p>${job.invoices.filter(i=>i.visibility!=='internal'&&i.document_status==='active').length>1?'Payments stay against their original saved invoices. Existing invoice history is preserved.':'Deposit and final payments stay on the original invoice number.'}</p></div>`);
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
    try {const d=await api('workflow/agencies/');if(!document.querySelector('[data-view=agencies].active'))return;app.innerHTML='<div class="heading"><div><span class="eyebrow">SEVLINK OPERATIONS</span><h1>Agencies</h1><p>Registered agencies, authorised portfolios and saved maintenance jobs.</p></div></div>'+d.agencies.map(a=>`<section class="panel"><h2>${esc(a.name)}</h2>${a.properties.map(p=>`<details class="panel"><summary><strong>${esc(p.address)}</strong> · ${esc(p.manager||'Agency managed')}</summary><p>Tenants: ${p.tenants.map(t=>esc(t.name)).join(', ')||'No active tenancy'}</p>${p.jobs.map(j=>`<article class="workflow-job-row"><span>${esc(j.reference)} · ${esc(j.title)} · ${esc(j.status)}</span><button class="secondary" data-agency-job="${j.id}">Open job</button></article>`).join('')}</details>`).join('')||'<p>No registered properties.</p>'}</section>`).join('');app.querySelectorAll('[data-agency-job]').forEach(b=>b.onclick=async()=>{try{showDetail(await api(`requests/${b.dataset.agencyJob}/`));}catch(e){toast(e.message);}});}catch(e){toast(e.message);}
  }
  return {icon,decorate,stages,inbox,job,agencies};
})();
