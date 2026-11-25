/* Visual enhancement only. Never constructs private costs or grants a workflow action. */
window.SevlinkCorporate=(()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label=(s)=>({unclassified:'Awaiting PM review',quoted:'Quotation required',callout:'Authorised call-out',pm:'Property manager',sevlink:'Sevlink'})[s]||s;
  function job({job,context,modal,panels,summary,show}){
    const w=job.workflow,tenant=context.user.role==='tenant';
    const icon=window.SevlinkWorkflowUI?.navIcon('requests')||'';
    const header=document.createElement('header');header.className='corporate-job-header';header.innerHTML=`${icon}<div><h1>${esc(job.official_job_reference?'Job: '+job.reference:'Request: '+job.reference)}</h1><p>${esc(job.category)} — ${esc(job.title)}</p></div>`;modal.prepend(header);
    // Keep prominent address/status/next action. Move supporting details to Overview.
    const detailBox=document.createElement('section');detailBox.className='panel corporate-job-details';
    const rows=[['Date reported',new Date(job.created_at).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short',timeZone:'Africa/Johannesburg'})],['Urgency',({normal:'Normal',high:'High',urgent:'Urgent',safety:'Historical safety flag'})[job.urgency]||job.urgency],['Job type',label(w.job_type)],...(!tenant?[['Access arranged by',label(w.access_responsibility)]]:[])];
    detailBox.innerHTML=`<h2>Job details</h2><dl>${rows.map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl>`;
    for(const element of [...summary.children]){
      if(element.matches('details,.job-access-notes')){detailBox.append(element);}
      else if(element.matches('p')&&element.querySelector('b')){element.remove();}
      else if(element.matches('span.eyebrow')){element.remove();}
      else if(element.matches('p')&&element.querySelector('small')){detailBox.append(element);}
    }
    const left=document.createElement('section'),right=document.createElement('section'),grid=document.createElement('div');grid.className='corporate-overview-grid';grid.append(left,right);left.append(detailBox);
    const attachments=[...panels.reports.querySelectorAll('.notice')].find(el=>el.querySelector('h2')?.textContent.startsWith('Job attachments'));
    if(attachments?.querySelector('h2')?.textContent.startsWith('Job attachments')){
      const box=document.createElement('section');box.className='panel';box.innerHTML='<h2>Attachments</h2><div class="corporate-thumb-list"></div>';
      const list=box.querySelector('div');for(const a of job.attachments){const link=document.createElement('a');link.className='corporate-thumbnail secondary';link.href=a.download_url;link.target='_blank';link.rel='noopener';if(a.content_type.startsWith('image/')){const img=document.createElement('img');img.src=a.download_url;img.alt=a.filename;img.loading='lazy';link.append(img);}const name=document.createElement('span');name.textContent=a.filename;link.append(name);list.append(link);}
      if(!job.attachments.length)list.textContent='No shared attachments yet.';
      const more=document.createElement('button');more.className='secondary';more.textContent='View reports & attachments';more.onclick=()=>show('reports');box.append(more);left.append(box);
    }
    const stops=tenant?[['Reported',['new','quoting','approval','declined','deposit_invoice','deposit','deposit_confirmation']],['PM review',[]],['Attendance',['ready','booked']],['Work underway',['underway']],['Completed',['invoice','payment','closed']],['Closed',[]]]:[['Reported',['new']],['PM review',['quoting']],['Quote approval',['approval','declined']],['Deposit',['deposit_invoice','deposit','deposit_confirmation']],['Attendance',['ready','booked']],['Completed',['underway','invoice','payment']],['Closed',['closed']]];
    let index=stops.findIndex(([,stages])=>stages.includes(w.stage));if(tenant){index=job.status==='closed'?5:job.status==='completed'?4:['on_site','in_progress'].includes(job.status)?3:job.status==='scheduled'?2:job.status==='awaiting_review'?0:1;}
    // A call-out and free-assessment route need not pass through every quote/deposit stage.
    const tracker=document.createElement('section');tracker.className='panel corporate-progress';tracker.innerHTML=`<h2>Job progress</h2><ol aria-label="Current job progress">${stops.map(([name],i)=>`<li class="${i===index?'current':i<index?'done':''}" ${i===index?'aria-current="step"':''}><span aria-hidden="true">${i<index?'✓':i===index?'●':''}</span>${esc(name)}</li>`).join('')}</ol><p class="muted" style="font-size:10px;margin-bottom:0">${job.status==='cancelled'?'This request is cancelled.':w.manual_stage?'Stage manually updated. Refer to saved payments and appointments for evidence.':w.job_type==='callout'?'Authorised call-out route. Quote and deposit steps depend on saved payment terms.':w.free_assessment?'Free quotation assessment. Repair authorisation remains required.':'Stage guide · Refer to the saved status and next required action.'}</p>`;
    right.append(tracker);
    const quick=document.createElement('div');quick.className='corporate-quick-actions';
    for(const [key,text]of [['comments','Add comment'],['quotes','View quote'],['invoices','View invoice'],['attendance','View attendance']]){if(!panels[key])continue;const b=document.createElement('button');b.className='secondary';b.type='button';b.textContent=text;b.onclick=()=>show(key);quick.append(b);}tracker.append(quick);
    if(!tenant){const info=document.createElement('section');info.className='panel corporate-key-info';info.innerHTML='<h2>Key information</h2>';const activeQuote=job.quotations.find(q=>q.status==='sent')||job.quotations.find(q=>q.approval_valid);const rows=[['Quotation',activeQuote?`${activeQuote.reference} · R ${Number(activeQuote.amount).toLocaleString('en-ZA',{minimumFractionDigits:2})}`:'Not yet issued'],['Deposit',w.deposit?`Verified allocation ${w.deposit.ready?'ready':'pending'} · R ${Number(w.deposit.required).toLocaleString('en-ZA',{minimumFractionDigits:2})} required`:'Not applicable'],['Attendance',w.attendance.find(a=>a.status==='confirmed')?.agreed_date||'Not yet confirmed']];for(const [name,value] of rows){const row=document.createElement('div');row.innerHTML=`<b>${esc(name)}</b><span>${esc(value)}</span>`;info.append(row);}right.append(info);}
    const identity=document.createElement('div');identity.className='corporate-summary-identity';
    const next=summary.querySelector(':scope > .professional-next-step');
    for(const el of [...summary.children]){
      if(el===next)continue;
      if(el.matches('.manual-move')){right.append(el);continue;}
      if(el.matches('.tenant-access-contacts')){detailBox.append(el);continue;}
      identity.append(el);
    }
    summary.prepend(identity);
    const rest=[...panels.overview.children];panels.overview.prepend(grid);rest.forEach(el=>right.append(el));
  }
  async function dashboard({api,context,app,showDetail,toast}){
    if(!document.querySelector('#nav [data-view="overview"].active'))return;
    app.querySelector('.corporate-recent-activity')?.remove();
    const panel=document.createElement('section');panel.className='panel corporate-recent-activity';panel.innerHTML='<h2>Recent activity</h2><p class="muted">Loading authorised updates…</p>';app.append(panel);
    try{
      const staff=context.user.role==='superadmin';
      if(!staff&&!['admin','pm','tenant'].includes(context.user.role)){panel.remove();return;}
      const data=await api(staff?'notifications/':'portal/updates/');if(!panel.isConnected)return;
      const rows=(data.items||data.updates||[]).slice(0,5);
      panel.innerHTML='<h2>Recent activity</h2>'+rows.map((row,i)=>`<article class="corporate-recent-row"><div><strong>${esc(row.event?.label||row.event||'Job update')}</strong><small>${esc(typeof row.property==='string'?row.property:row.property?.address||'')} · ${esc(new Date(row.at||row.event?.at).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short',timeZone:'Africa/Johannesburg'}))}</small></div><button class="secondary" data-recent-update="${i}">View update →</button></article>`).join('')+(rows.length?'':'<p class="muted">No recent updates yet.</p>');
      panel.querySelectorAll('[data-recent-update]').forEach(button=>button.onclick=async()=>{try{const row=rows[Number(button.dataset.recentUpdate)];showDetail(await api(`requests/${row.job||row.job_id||row.id}/`));}catch(error){toast(error.message);}});
    }catch(error){if(panel.isConnected)panel.innerHTML='<h2>Recent activity</h2><p class="muted">Updates are temporarily unavailable. Refresh to try again.</p>';}
  }
  return {job,dashboard};
})();
