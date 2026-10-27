/* Authenticated adapter for the existing portal shell. No demo state or role switching. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date = value => new Date(value).toLocaleString('en-ZA', {dateStyle:'medium', timeStyle:'short', timeZone:'Africa/Johannesburg'});
  const badge = value => `<span class="badge ${esc(value.split(' ')[0])}">${esc(value)}</span>`;
  const app = $('#app'), modal = $('#modal');
  let detailGeneration = 0;
  let context, jobs = [], total = 0, page = 1, next = null, view = 'overview', selected, toastTimer;
  const csrf = () => document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice(10) || '';
  function toast(message) {
    $('#toast').textContent = message; $('#toast').hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6000);
  }
  async function api(path, options = {}) {
    const response = await fetch('/api/maintenance/' + path, {
      ...options, credentials:'same-origin', cache:'no-store',
      headers:{...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), 'X-CSRFToken':csrf(), ...options.headers}
    });
    if (response.status === 401) { location.assign('/login/?next=' + encodeURIComponent(location.pathname + location.search)); throw Error('Please sign in again.'); }
    let data;
    try { data = await response.json(); } catch { throw Error('The server could not process this request. Please try again.'); }
    if (!response.ok) {
      const fields = data.fields ? Object.entries(data.fields).map(([field, errors]) => `${field}: ${errors.map(e => e.message).join(' ')}`).join(' ') : '';
      throw Error(fields || data.error || 'The request could not be saved.');
    }
    return data;
  }
  let loadGeneration=0, registerMetadata={}, registerTimer;
  const defaultRegister=()=>({search:'',bucket:'all',property:'',agency:'',status:'',stage:'',category:'',urgency:'',sort:'newest'});
  let registerFilters=defaultRegister();
  async function loadJobs() {
    const active=view,generation=++loadGeneration,params=new URLSearchParams({page});
    if(active==='requests'){params.set('register','1');for(const [k,v] of Object.entries(registerFilters))if(v)params.set(k,v);}
    const data = await api('requests/?'+params);
    if(active!==view || generation!==loadGeneration)return false;
    jobs = data.results; total = data.count; next = data.next;registerMetadata=data.register||{};return true;
  }
  const heading = (title, sub) => `<div class="heading"><div><span class="eyebrow">${['superadmin','operations'].includes(context.user.role) ? 'SEVLINK OPERATIONS' : 'PROPERTY MAINTENANCE'}</span><h1>${title}</h1><p style="margin:0">${sub}</p></div></div>`;
  function shell() {
    document.body.dataset.portalRole=context.user.role;
    const pmItems=[['overview','◫','Overview'],['requests','☷','Repair jobs'],['properties','⌂','Properties'],['tenants','♙','Tenants'],['profile','⚙','Agency profile'],['report','＋','Report a repair'],['publicCalendar','▦','Maintenance calendar'],['updates','✉','Updates & reminders'],['quotes','▤','Quotations'],['accounts','R','Accounts & Payments'],['issues','⚑','Report Website Issue']];
    const tenantItems=[['overview','◫','Overview'],['requests','☷','My Repairs'],['report','＋','Report a Repair'],['properties','⌂','My Property'],['publicCalendar','▦','Maintenance Calendar'],['updates','◷','Updates & Notifications'],['issues','⚑','Report Website Issue']];
    const items = context.user.role==='tenant'?tenantItems:['pm','admin'].includes(context.user.role)?pmItems:[['overview','◫','Overview'],['requests','☷','Repair jobs'],...(context.user.role==='superadmin'?[['agencies','⌖','Agencies'],['websiteIssues','⚑','Website Issues']]:[]),...(context.can_schedule?[['calendar','▦','Weekly calendar']]:[]),...(context.can_supplier_payments?[['monday','R','Payments'],['regions','♙','Subcontractors']]:[])];
    $('#nav').innerHTML=items.map(([key,icon,label])=>`<button data-view="${key}" class="${view===key?'active':''}" aria-current="${view===key?'page':'false'}">${icon} &nbsp; ${label}</button>`).join('');
    $('.profile').innerHTML = `<span class="demo">SIGNED IN</span><span class="name">${esc(context.user.name)}<br><small>${esc({superadmin:'Sevlink Super Admin',operations:'Sevlink Operations',admin:'Agency administrator',pm:'Property manager',tenant:'Tenant'}[context.user.role])}</small></span>${context.user.role === 'superadmin' ? '<button class="secondary" id="notifications" aria-label="Operations notifications">🔔 Notifications</button>' : ''}<button class="secondary" id="logout">Sign out</button>`;
    if ($('#notifications')) { $('#notifications').onclick = () => notificationCentre(); notificationCount(); }
    if(['pm','admin','tenant'].includes(context.user.role)){
      const updates=document.createElement('button');updates.className='secondary';updates.id='userNotifications';updates.setAttribute('aria-label','Job notifications');updates.textContent='Updates';$('.profile').insertBefore(updates,$('#logout'));updates.onclick=()=>{view='updates';render();};api('workflow/notifications/').then(d=>{if(updates.isConnected)updates.textContent=`Updates (${d.unread})`;}).catch(e=>toast(e.message));
    }
    $('#logout').onclick = async () => {
      try {
        const response = await fetch('/logout/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}});
        if (!response.ok) throw Error('Sign out failed. Please try again.');
        location.assign('/login/');
      } catch (error) { toast(error.message); }
    };
    if(context.user.role==='superadmin'){const first=$('#nav [data-view=monday]');if(first)first.insertAdjacentHTML('beforebegin','<span class="nav-heading">FINANCE</span>');}
    window.SevlinkWorkflowUI?.decorate();
    $('#breadcrumb').textContent = items.find(item=>item[0]===view)?.[2] || 'Overview';
    if (!$('#phoneBar')) {
      document.body.insertAdjacentHTML('beforeend', '<div id="phoneBar"></div><nav id="phoneNav" aria-label="Phone navigation"></nav><button id="phoneShade" aria-label="Close navigation menu"></button>');
    }
    $('#phoneBar').innerHTML = '<a class="phone-brand" href="/maintenance/">SEVLINK<span>PROPERTY MAINTENANCE</span></a><button id="phoneMenuButton" aria-label="Open navigation menu" aria-expanded="false">☰ Menu</button>';
    $('#phoneNav').classList.toggle('customer-nav', ['admin','pm','tenant'].includes(context.user.role));
    $('#phoneNav').innerHTML = items.map(([key, icon, label]) => `<button data-view="${key}" class="${view === key ? 'active' : ''}"><span aria-hidden="true">${icon}</span>${label}</button>`).join('');
    $('#phoneMenuButton').onclick = () => {
      const open = document.body.classList.toggle('phone-menu-open');
      $('#phoneMenuButton').setAttribute('aria-expanded', String(open));
    };
    window.SevlinkWorkflowUI?.decorate();
    $('#phoneShade').onclick = () => {
      document.body.classList.remove('phone-menu-open');
      $('#phoneMenuButton').setAttribute('aria-expanded', 'false');
    };

  }
  function list() {
    if(view==='requests')return registerList();
    const title = view==='requests'?(context.user.role==='tenant'?'Your repair history.':'Repair job register.'):context.user.role==='tenant'?'Your home. Your repairs.':'Every repair. One clear record.';
    app.innerHTML = heading(title, context.user.role==='tenant' ? 'Report a repair and follow updates from your property manager.' : 'Review maintenance requests and keep their status up to date.') +
      `<div class="stats">${[['Repair requests', total, 'Visible to your account'],['On this page', jobs.length, 'Up to 50 requests per page']].map(([label, number, help]) => `<div class="stat"><label>${label}</label><strong>${number}</strong><small>${help}</small></div>`).join('')}</div>` +
      '<div class="panel" style="margin-top:26px"><div class="panelhead"><h2>Repair jobs</h2><button class="secondary" id="refresh">Refresh</button></div><div class="filters repair-register-search"><input id="search" aria-label="Search requests on this page" placeholder="Search this page by repair or property"><select id="statusFilter" aria-label="Filter status"><option value="">All statuses</option>' + [...new Set(jobs.map(j => j.status_label))].map(s => `<option>${esc(s)}</option>`).join('') + '</select></div><div class="tablewrap"><table class="phone-cards repair-register-table"><thead><tr><th>PROPERTY / REPAIR</th><th>STATUS</th><th>PRIORITY</th><th>REPORTED</th><th></th></tr></thead><tbody id="rows"></tbody></table></div><div class="toolbar" style="margin-top:18px"><button class="secondary" id="previous" ' + (page === 1 ? 'disabled' : '') + '>← Previous</button><span>Page ' + page + '</span><button class="secondary" id="next" ' + (next === null ? 'disabled' : '') + '>Next →</button></div></div>';
    function rows() {
      const query = $('#search').value.toLowerCase(), status = $('#statusFilter').value;
      $('#rows').innerHTML = jobs.filter(j => (!status || j.status_label === status) && `${j.reference} ${j.legacy_reference || ''} ${j.title} ${j.property.address} ${j.property.name} ${j.property.agency}`.toLowerCase().includes(query)).map(j =>
        `<tr><td data-label="PROPERTY / REPAIR"><strong>${esc(j.property.address)}</strong><small>${esc(j.property.name)} · ${esc(j.property.agency)}</small><p style="margin:7px 0 2px;color:var(--ink)">${esc(j.title)}</p><small>${esc(j.reference)} · ${esc(j.category)}</small></td><td data-label="STATUS">${badge(j.status_label)}</td><td data-label="PRIORITY">${badge(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[j.urgency]||'Not set')}</td><td data-label="REPORTED">${esc(date(j.created_at))}</td><td data-label="OPEN"><button class="secondary" data-job="${j.id}">Open job →</button></td></tr>`).join('') || '<tr><td colspan="5" class="empty">No repair jobs to show.</td></tr>';
    }
    $('#search').oninput = rows; $('#statusFilter').onchange = rows; rows();
    $('#refresh').onclick = () => refresh();
    $('#previous').onclick = () => refresh(page - 1);
    $('#next').onclick = () => refresh(next);
  }
  function registerList(){
    const meta=registerMetadata,f=registerFilters,staff=context.user.role==='superadmin';
    const options=(items,value,all)=>`<option value="">${esc(all)}</option>`+items.map(i=>`<option value="${esc(i.id??i.value)}" ${(i.id??i.value)===value?'selected':''}>${esc(i.label)}</option>`).join('');
    const filter=(id,label,items,value,all)=>`<label>${label}<select id="${id}">${options(items,value,all)}</select></label>`;
    app.innerHTML=heading(context.user.role==='tenant'?'Your repair history.':'Repair job register.','Search authorised repair requests and job history across all result pages.')+`<section class="panel"><div class="filters repair-register-search"><input id="search" type="search" aria-label="Search repair jobs" placeholder="Search reference, property address or repair…" value="${esc(f.search)}"><button class="secondary" id="clearRegister">Clear filters</button></div><div class="repair-register-filters">${staff?filter('registerAgency','Agency',meta.agencies||[],f.agency,'All agencies'):''}${filter('registerProperty','Property',meta.properties||[],f.property,'All properties')}${staff?filter('registerStage','Pipeline stage',meta.stages||[],f.stage,'All stages'):filter('statusFilter','Status',meta.statuses||[],f.status,'All statuses')}${filter('registerCategory','Category',(meta.categories||[]).map(c=>({id:c,label:c})),f.category,'All categories')}${filter('registerUrgency','Priority',[['normal','Normal'],['high','High'],['urgent','Urgent'],['safety','Safety']].map(([id,label])=>({id,label})),f.urgency,'All priorities')}${filter('registerSort','Sort by',[['newest','Newest first'],['oldest','Oldest first'],['property','Property address']].map(([id,label])=>({id,label})),f.sort,'Default order')}</div><div class="toolbar repair-register-buckets" style="margin-top:20px">${[['all','All jobs'],['open','Open'],['closed','Closed'],['cancelled','Cancelled']].map(([key,label])=>`<button class="${f.bucket===key?'primary':'secondary'}" data-register-bucket="${key}">${label} · ${meta.buckets?.[key]??0}</button>`).join('')}</div><p class="muted" aria-live="polite">${total} matching jobs · Page ${page}${jobs.length?' · showing '+((page-1)*50+1)+'–'+((page-1)*50+jobs.length):''}</p><div class="tablewrap"><table class="phone-cards repair-register-table"><thead><tr><th>PROPERTY / REPAIR</th>${staff?'<th>AGENCY / PM</th>':''}<th>STATUS</th><th>PRIORITY</th><th>REPORTED</th><th></th></tr></thead><tbody id="rows">${jobs.map(j=>`<tr><td data-label="PROPERTY / REPAIR"><strong>${esc(j.property.address)}</strong><small>${esc(j.property.name)}</small><p style="margin:7px 0 2px;color:var(--ink)">${esc(j.title)}</p><small>${esc(j.reference)} · ${esc(j.category)}</small></td>${staff?`<td data-label="AGENCY / PM"><strong>${esc(j.property.agency)}</strong><small>PM: ${esc(j.property.manager)}</small></td>`:''}<td data-label="STATUS">${badge(staff?(meta.stages||[]).find(s=>s.id===j.workflow.stage)?.label||j.status_label:j.status_label)}</td><td data-label="PRIORITY">${badge(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[j.urgency]||'Not set')}</td><td data-label="REPORTED">${esc(date(j.created_at))}</td><td data-label="OPEN"><button class="secondary" data-job="${j.id}">Open job →</button></td></tr>`).join('')||`<tr><td colspan="${staff?6:5}" class="empty">No jobs match these filters.</td></tr>`}</tbody></table></div><div class="toolbar" style="margin-top:18px"><button class="secondary" id="previous" ${page===1?'disabled':''}>← Previous</button><span>Page ${page}</span><button class="secondary" id="next" ${next===null?'disabled':''}>Next →</button><button class="secondary" id="refresh">Refresh</button></div></section>`;
    $('#clearRegister').onclick=()=>{clearTimeout(registerTimer);registerFilters=defaultRegister();refresh(1);};
    $('#search').oninput=e=>{f.search=e.target.value;const caret=e.target.selectionStart;clearTimeout(registerTimer);registerTimer=setTimeout(async()=>{if(view!=='requests')return;await refresh(1);if(view==='requests'){$('#search').focus();$('#search').setSelectionRange(caret,caret);}},250);};
    for(const [id,key] of [['registerAgency','agency'],['registerProperty','property'],['statusFilter','status'],['registerStage','stage'],['registerCategory','category'],['registerUrgency','urgency'],['registerSort','sort']]){const input=$('#'+id);if(input)input.onchange=e=>{clearTimeout(registerTimer);f[key]=e.target.value;if(key==='agency')f.property='';refresh(1);};}
    app.querySelectorAll('[data-register-bucket]').forEach(b=>b.onclick=()=>{clearTimeout(registerTimer);f.bucket=b.dataset.registerBucket;refresh(1);});
    $('#previous').onclick=()=>refresh(page-1);$('#next').onclick=()=>refresh(next);$('#refresh').onclick=()=>refresh();
  }
  async function refresh(newPage = page) {
    const oldPage = page;
    try { page = newPage; if(await loadJobs()!==false)render(); }
    catch (error) { page = oldPage; toast(error.message); }
  }
  const icons = {'Plumbing':'🚰','Electrical':'💡','Doors & locks':'🚪','Painting':'🖌','Tiling':'▦'};
  function reportLanding() {
    app.innerHTML = heading('What needs attention?', 'A few clear details help your property manager review the repair.') + '<div class="reportwrap"><div class="panel"><div class="step-label">01 / SELECT A REPAIR CATEGORY</div><div class="categorygrid">' + context.categories.map(c => `<button class="category illustrated" data-category="${esc(c)}"><span>${window.SevlinkWorkflowUI?.icon(context.categories.indexOf(c)) || ''}</span><b>${esc(c)}</b><small>Tell us what happened →</small></button>`).join('') + '</div><div class="notice">For immediate danger, use your established emergency contact. This portal does not dispatch emergency assistance.</div></div></div>';
  }
  function render() { shell(); if (view === 'report') reportLanding(); else if(view==='agencies')window.SevlinkWorkflowUI?.agencies({api,app,showDetail,toast});else if (view === 'regions') regionalWorkspace(); else if(view==='calendar')weeklyCalendar();else if(view==='monday')mondayPayments();else if(['properties','tenants','quotes','accounts','publicCalendar','updates','profile','issues','websiteIssues'].includes(view))customerPage();else if(view==='overview'){if(customerRole())customerOverview();else{list();window.SevlinkWorkflowUI?.stages({api,app,showDetail,toast,context});}}else list(); }
  function reportForm(category) {
    if (!context.properties.length) { toast('Your account needs an active property link. Contact your property manager.'); return; }
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">${esc(category)}</span><h1>Report a problem.</h1><form id="reportForm"><label>Your property</label><select name="property" required>${context.properties.map(p => `<option value="${p.id}">${esc(p.name)} · ${esc(p.address)}</option>`).join('')}</select><label>What is the problem?</label><input name="title" required maxlength="180"><label>Tell us what happened</label><textarea name="description" required rows="4" maxlength="2500" placeholder="Where is the issue, when did it start, and what can you see?"></textarea><label>Safety concern</label><select name="urgency"><option value="normal">No immediate safety concern flagged</option><option value="safety">Flag a safety concern for urgent review</option></select><label>Relevant access information</label><textarea name="access_information" maxlength="2500"></textarea><label>Photos or documents (optional)</label><input name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><small>Up to 5 files, 5 MB each · JPEG, PNG, WebP or PDF.</small><div class="notice">Your report goes to your property manager for review. Attachments are shared with your property manager and Sevlink.</div><p id="formError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Send report to property manager</button></div></form>`;
    modal.showModal();
    const submissionKey = crypto.randomUUID();
    $('#reportForm').onsubmit = async event => {
      event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
      try {
        const data = new FormData(event.target); data.set('category', category);
        for (const file of data.getAll('attachments')) { if (file.size > 5 * 1024 * 1024) throw Error('Each file must be at most 5 MB.'); }
        if (data.getAll('attachments').filter(file => file.size).length > 5) throw Error('Choose at most five files.');
        if (!data.getAll('attachments').some(file => file.size)) data.delete('attachments');
        await api('requests/', {method:'POST', body:data, headers:{'Idempotency-Key':submissionKey}});
        modal.close(); view = 'requests'; page = 1;
        try { await loadJobs(); render(); toast('Report saved and sent for property manager review.'); }
        catch { render(); toast('Report saved. Refresh the list to see it.'); }
      } catch (error) { $('#formError').hidden = false; $('#formError').textContent = error.message; }
      finally { if (button.isConnected) button.disabled = false; }
    };
  }
  function quoteFields(q = {}, upload = true) {
    return `<label>Quotation reference printed on uploaded PDF (entered manually — verify it matches the PDF)</label><input name="reference" required maxlength="80" value="${esc(q.reference || '')}"><label>Recorded total (ZAR)</label><input name="amount" required type="number" min="0.01" max="9999999999.99" step="0.01" value="${esc(q.amount || '')}"><label>Title</label><input name="title" required maxlength="180" value="${esc(q.title || '')}"><label>Scope shared with the agency</label><textarea name="scope" maxlength="3000">${esc(q.scope || '')}</textarea>${upload ? '<label>Externally prepared quotation PDF</label><input name="attachments" type="file" required accept="application/pdf"><small>One PDF, up to 5 MB. Upload only the agency-facing Sevlink quotation. Keep subcontractor documents in Operations-only notes.</small>' : '<small>The uploaded PDF cannot be replaced. Upload a new revision to change the document.</small>'}`;
  }
  const errorMarkup = '<p class="collaborationError" role="alert" hidden></p>';
  function refundForm(i,p) {
    return `<form class="invoiceRefund" data-invoice="${i.id}" data-version="${i.version}"><h2>Record refund against payment ${p.id}</h2><input type="hidden" name="payment_id" value="${p.id}"><label>Refund amount (ZAR), eligible ${esc(p.refundable)}</label><input name="amount" required type="number" min="0.01" max="${esc(p.refundable)}" step="0.01"><label>Refund date</label><input name="refunded_on" type="date" required><label>Refund reference (Operations only)</label><input name="reference" maxlength="180" required><label>Reason (Operations only)</label><textarea name="reason" maxlength="1000" required></textarea><label>Type REFUND to confirm this manual accounting entry</label><input name="confirmation" pattern="REFUND" required>${errorMarkup}<button type="submit" class="secondary">Record manual refund</button></form>`;
  }
  function invoiceAdjustments(i) {
    const voidForm = i.document_status === 'active' ? `<form class="invoiceVoid" data-invoice="${i.id}" data-version="${i.version}"><h2>Void invoice</h2><label>Reason (Operations only)</label><textarea name="reason" required maxlength="1000"></textarea><label>Void date</label><input type="date" name="voided_on" required><label>External accounting adjustment reference</label><input name="accounting_reference" required maxlength="180"><label><input name="accounting_reviewed" type="checkbox" required> External accounting documents/tax treatment reviewed with the responsible accountant</label><label>Type VOID to confirm</label><input name="confirmation" required pattern="VOID">${errorMarkup}<button type="submit" class="secondary">Void invoice record</button></form>` : `<p>Voided ${esc(i.voided_on || '')}: ${esc(i.void_reason)} · ${esc(i.voided_by || '')}</p>`;
    const correction = i.document_status === 'void' && !i.replacement_id ? `<form class="invoiceCorrection" data-invoice="${i.id}" data-version="${i.version}"><h2>Upload corrected replacement invoice</h2><label>External invoice number printed on PDF</label><input name="number" required maxlength="80"><label>Recorded amount (ZAR)</label><input name="amount" required type="number" min="0.01" step="0.01"><label>Due date</label><input type="date" name="due_date" required><label>Correction reason (Operations only)</label><textarea name="reason" required maxlength="1000"></textarea><label>Externally prepared replacement PDF</label><input type="file" name="attachments" accept="application/pdf" required>${errorMarkup}<button class="secondary" type="submit">Upload corrected invoice</button></form>` : '';
    const hold = i.reconciliation_required ? `<div class="notice">Reconciliation hold: no payment collection. Preserve original receipts; refund any original funds and resolve the original hold first.</div><form class="invoiceReconcile" data-invoice="${i.id}" data-version="${i.version}"><label>Reconciliation reason</label><textarea name="reason" required maxlength="1000"></textarea><label>External reconciliation reference</label><input name="reference" required maxlength="180"><label>Type RECONCILE to confirm</label><input name="confirmation" required pattern="RECONCILE">${errorMarkup}<button class="secondary" type="submit">Resolve reconciliation hold</button></form>` : '';
    const credit = `<form class="invoiceCredit" data-invoice="${i.id}" data-version="${i.version}"><h2>Record externally issued credit note</h2><label>Reference printed on credit note</label><input name="reference" required maxlength="80"><label>Recorded amount (ZAR)</label><input name="amount" type="number" min="0.01" step="0.01" required><label>Issue date</label><input type="date" name="issued_on" required><label>Reason (Operations only)</label><textarea name="reason" maxlength="1000" required></textarea><label>Externally prepared PDF</label><input name="attachments" type="file" accept="application/pdf" required><small>Same visibility as this invoice. This records paperwork; it does not create a tax document or change the payment ledger.</small>${errorMarkup}<button type="submit" class="secondary">Upload credit note PDF</button></form>`;
    return `${hold}${voidForm}${correction}${credit}${i.financial_history.map(a => `<p><small>${esc(a.type)} · ${esc(a.actor)} · ${esc(date(a.at))} · ${esc(a.reason)} · ${esc(a.reference)}</small></p>`).join('')}`;
  }
  function invoiceMarkup(job) {
    if (context.user.role === 'tenant') return '';
    const operations = context.user.role === 'superadmin';
    return `<h2>Invoices &amp; payment status</h2><p>Record the deposit and remaining balance against the same invoice. Keep its original total and document; do not upload it again to record a payment.</p>${operations?'<button class="primary" id="showInvoiceUpload" type="button">＋ Upload invoice</button>':''}${job.invoices.map(i => `<div class="card" data-record-id="${i.id}"><h2>${esc(i.number)}${i.visibility === 'internal' ? ' · Operations only' : ''}</h2><p>PDF invoice number: ${esc(i.number)}</p><h2>ZAR ${esc(i.amount)}</h2><p>Due ${esc(i.due_date)} · Uploaded ${esc(date(i.uploaded_at))}</p>${badge(i.document_status)} ${badge(i.payment_status)}<p>Gross payments ZAR ${esc(i.paid_amount)} · Refunds ZAR ${esc(i.refunded_amount)} · Net paid ZAR ${esc(i.net_paid_amount)}<br>Outstanding ZAR ${esc(i.outstanding)} · Collectible ZAR ${esc(i.collectible)}</p>${i.previous_id ? '<p>Corrected replacement — original document retained in job history.</p>' : ''}${i.replacement_id ? '<p>Replacement invoice recorded; this original remains in history.</p>' : ''}<a class="secondary" href="${esc(i.document.download_url)}" download>Download invoice PDF</a>${i.credit_notes.map(n => `<p>External credit note ${esc(n.reference)} · ZAR ${esc(n.amount)} · <a href="${esc(n.document.download_url)}" download>Download credit note PDF</a></p>`).join('')}${i.payments.map(p => `<p>Manual payment: ZAR ${esc(p.amount)} · ${esc(p.paid_on)}${operations ? `<br><small>${esc(p.actor)} · ${esc(p.reference)} ${esc(p.note)}</small>` : ''}</p>${operations && Number(p.refundable)>0 ? refundForm(i,p) : ''}`).join('')}${i.refunds.map(r => `<p>Manual refund ZAR ${esc(r.amount)} · ${esc(r.refunded_on)}${operations ? `<br><small>${esc(r.actor)} · ${esc(r.reason)} · ${esc(r.reference)}</small>` : ''}</p>`).join('')}${i.reconciliation_required && !operations ? '<div class="notice">Payment collection is on reconciliation hold.</div>' : ''}${operations && i.document_status === 'active' && !i.reconciliation_required && i.payment_status !== 'paid' ? `<form class="invoicePayment" data-invoice="${i.id}" data-version="${i.version}"><label>Received payment amount (ZAR)</label><input name="amount" type="number" required min="0.01" max="${esc(i.outstanding)}" step="0.01"><label>Payment date</label><input name="paid_on" required type="date"><label>Payment reference (Operations only)</label><input name="reference" maxlength="180"><label>Private payment note</label><textarea name="note" maxlength="1000"></textarea>${errorMarkup}<button class="secondary" type="submit">Record manual payment</button></form>` : ''}${operations ? invoiceAdjustments(i) : ''}</div>`).join('') || '<p>No invoices uploaded yet.</p>'}<div class="notice">Uploading proof of payment does not mark an invoice paid. Sevlink verifies received money before recording a payment.</div>${operations ? `<form id="invoiceForm" hidden><h2>Upload invoice PDF</h2><label>Visibility — select carefully</label><select name="visibility"><option value="internal">Operations only — private subcontractor invoice</option><option value="shared">Agency-visible Sevlink invoice</option></select><label>Invoice type (agency-visible invoices)</label><select name="purpose"><option value="deposit" ${job.status!=='completed'?'selected':''}>Deposit invoice</option><option value="final" ${job.status==='completed'?'selected':''}>Final invoice</option></select><small>Operations-only invoices are always recorded as private supplier invoices.</small><label>Invoice number printed on uploaded PDF (entered manually — verify it matches the PDF)</label><input name="number" required maxlength="80"><label>Recorded total (ZAR)</label><input name="amount" type="number" required min="0.01" max="9999999999.99" step="0.01"><label>Due date</label><input name="due_date" required type="date"><label>Externally prepared invoice PDF</label><input name="attachments" type="file" required accept="application/pdf"><small>One PDF, up to 5 MB. Payments are recorded manually after upload.</small><p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Upload invoice PDF</button></form>` : ''}`;
  }
  function collaborationMarkup(job) {
    const canDecide = ['pm','admin'].includes(context.user.role), operations = context.user.role === 'superadmin', open = !['completed','cancelled','closed'].includes(job.status);
    const quotations = context.user.role === 'tenant' ? '' : `<h2>Quotations</h2>${job.quotations.map(q => `<div class="card" data-record-id="${q.id}"><h2>${esc(q.title)} · Revision ${q.revision}</h2><p>Quotation reference printed on PDF: ${esc(q.reference)}</p>${q.status === 'approved' ? `<div class="notice">${q.approval_valid ? 'Current approval remains valid until a replacement is approved.' : 'Historical approval — replaced only after the linked amendment was approved.'}</div>` : ''}${q.amends_id ? `<p>Amends previously approved quotation ${esc(q.amends_reference || q.amends_id)}. The original approval remains valid while this amendment is pending/rejected.</p><p>${esc(q.amendment_reason)}</p>` : ''}<p style="white-space:pre-wrap">${esc(q.scope)}</p><h2>ZAR ${esc(q.amount)}</h2>${badge(q.status)}${q.decision_reason ? `<p>${esc(q.decision_reason)}</p>` : ''}${q.document ? `<p>Uploaded ${esc(date(q.document.uploaded_at))}</p><p><a class="secondary" href="${esc(q.document.download_url)}" download>Download quotation PDF</a></p>` : '<p>Legacy quotation record — no uploaded PDF. No document is generated.</p>'}${q.history.map(h => `<small>${esc(h.action)} · ${esc(h.actor)} · ${esc(date(h.at))}${h.reason ? ' · ' + esc(h.reason) : ''}</small><br>`).join('')}${q.document && q.status === 'sent' && canDecide && open ? `<form class="quoteDecision" data-quote="${q.id}" data-version="${q.version}"><label>Decision</label><select name="status"><option value="approved">Approve</option><option value="rejected">Reject</option><option value="revision_requested">Request revision</option></select><label>Decision comment</label><textarea name="reason" required maxlength="1000"></textarea><p class="collaborationError" role="alert" hidden></p><button class="primary" type="submit">Save quotation decision</button></form>` : ''}${operations && q.document && q.status === 'draft' && open ? `<form class="quoteEdit" data-quote="${q.id}" data-version="${q.version}">${quoteFields(q,false)}<p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Save draft details</button></form><button class="primary quoteAction" data-quote="${q.id}" data-version="${q.version}" data-action="send">Send for approval</button>` : ''}${operations && q.approval_valid && !q.has_next_revision && open ? `<form class="quoteAmendment" data-quote="${q.id}" data-version="${q.version}"><h2>Request approved quotation amendment</h2>${quoteFields(q)}<label>Amendment reason shared with agency</label><textarea name="reason" required maxlength="1000"></textarea>${errorMarkup}<button class="secondary" type="submit">Upload quotation amendment</button></form>` : ''}${operations && ['sent','rejected','revision_requested'].includes(q.status) && open ? `<form class="quoteRevision" data-quote="${q.id}" data-version="${q.version}"><h2>Upload next revision</h2>${quoteFields(q)}<p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Upload revised quotation</button></form>` : ''}</div>`).join('') || '<p>No quotations yet.</p>'}`;
    const issue = operations && open ? `<form id="quoteForm"><h2>Upload quotation PDF</h2>${quoteFields()}<p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Save quotation draft</button></div></form>` : '';
    const canComment = context.user.role !== 'tenant' || job.tenant_comments_allowed;
    return `${quotations}${issue}${invoiceMarkup(job)}${operations ? `<p><button class="secondary" id="tenantConversation">${job.tenant_comments_allowed ? 'Disable' : 'Enable'} tenant conversation access</button></p>` : ''}<h2 style="margin-top:20px">Job conversation</h2>${job.comments.map(c => `<div class="comment"><b>${esc(c.actor)}${c.visibility === 'internal' ? ' · Operations only' : ''}</b><p style="white-space:pre-wrap">${esc(c.text)}</p><small>${esc(date(c.at))}</small>${c.attachments.map(a => `<p><a href="${esc(a.download_url)}" download>${esc(a.filename)}</a></p>`).join('')}</div>`).join('') || '<p>No comments yet.</p>'}${canComment ? `<form id="commentForm"><label>Comment</label><textarea name="text" required maxlength="2500" rows="3"></textarea>${context.user.role!=='tenant'?'<label>Message audience</label><select name="visibility"><option value="agency">Sevlink Operations Only / private PM discussion</option><option value="shared">Sevlink Operations and Tenant</option>'+ (operations?'<option value="internal">Sevlink internal note</option>':'')+'</select>':''}<label>Photos or documents (optional)</label><input name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Add comment</button></div></form>` : '<p>Tenant conversation access is disabled for this job.</p>'}`;
  }
  function wireCollaboration(job) {
    const invoiceUploadButton=$('#showInvoiceUpload'),invoiceUploadForm=$('#invoiceForm');
    if(invoiceUploadButton && invoiceUploadForm){
      invoiceUploadButton.setAttribute('aria-expanded','false');
      invoiceUploadButton.setAttribute('aria-controls','invoiceForm');
      invoiceUploadButton.onclick=()=>{invoiceUploadForm.hidden=!invoiceUploadForm.hidden;invoiceUploadButton.setAttribute('aria-expanded',String(!invoiceUploadForm.hidden));if(!invoiceUploadForm.hidden)invoiceUploadForm.scrollIntoView({block:'nearest'});};
    }
    if ($('#tenantConversation')) $('#tenantConversation').onclick = async () => { try { await api(`requests/${job.id}/conversation-permissions/`, {method:'POST',body:JSON.stringify({version:job.version,tenant_comments_allowed:!job.tenant_comments_allowed})}); showDetail(await api(`requests/${job.id}/`)); } catch (error) { toast(error.message); } };
    modal.querySelectorAll('.quoteAction').forEach(button => {
      const key = crypto.randomUUID();
      button.onclick = async () => {
        button.disabled = true;
        try { await api(`requests/${job.id}/quotations/${button.dataset.quote}/${button.dataset.action}/`, {method:'POST', body:JSON.stringify({version:Number(button.dataset.version)}), headers:{'Idempotency-Key':key}}); showDetail(await api(`requests/${job.id}/`)); toast('Quotation saved.'); }
        catch (error) { toast(error.message); button.disabled = false; }
      };
    });
    const forms = [[$('#invoiceForm'), `requests/${job.id}/invoices/`], [$('#commentForm'), `requests/${job.id}/comments/`], [$('#quoteForm'), `requests/${job.id}/quotations/`],
      ...Array.from(modal.querySelectorAll('.quoteDecision')).map(form => [form, `requests/${job.id}/quotations/${form.dataset.quote}/decision/`]),
      ...Array.from(modal.querySelectorAll('.quoteEdit')).map(form => [form, `requests/${job.id}/quotations/${form.dataset.quote}/edit/`]),
      ...Array.from(modal.querySelectorAll('.quoteRevision')).map(form => [form, `requests/${job.id}/quotations/${form.dataset.quote}/revise/`]),
      ...Array.from(modal.querySelectorAll('.invoicePayment')).map(form => [form, `requests/${job.id}/invoices/${form.dataset.invoice}/payments/`]),
      ...Array.from(modal.querySelectorAll('.quoteAmendment')).map(form => [form, `requests/${job.id}/quotations/${form.dataset.quote}/amend/`]),
      ...[['invoiceRefund','refunds'],['invoiceVoid','void'],['invoiceCorrection','correct'],['invoiceCredit','credit-notes'],['invoiceReconcile','reconcile']].flatMap(([cls,action]) => Array.from(modal.querySelectorAll('.'+cls)).map(form => [form, `requests/${job.id}/invoices/${form.dataset.invoice}/${action}/`]))];
    for (const [form, path] of forms) {
      if (!form) continue;
      let key = crypto.randomUUID(), priorBody;
      form.onsubmit = async event => {
        event.preventDefault(); const button = form.querySelector('[type=submit]'); button.disabled = true;
        try {
          let body;
          if (form.id === 'commentForm' || form.id === 'quoteForm' || form.id === 'invoiceForm' || ['quoteRevision','quoteAmendment','invoiceCorrection','invoiceCredit'].some(cls => form.classList.contains(cls))) {
            body = new FormData(form);
            if (form.dataset.version) body.set('version', form.dataset.version);
            if (!body.getAll('attachments').some(file => file.size)) body.delete('attachments');
          } else {
            const data = Object.fromEntries(new FormData(form));
            if (form.dataset.version) data.version = Number(form.dataset.version);
            if (form.querySelector('[name=accounting_reviewed]')) data.accounting_reviewed = form.querySelector('[name=accounting_reviewed]').checked;
            if (data.payment_id) data.payment_id = Number(data.payment_id);
            if (['invoiceRefund','invoiceVoid','invoiceReconcile'].some(cls => form.classList.contains(cls)) && !window.confirm('Confirm this manual accounting adjustment. No bank transfer or tax document is generated. Original files and ledger entries remain in history.')) return;
            body = JSON.stringify(data);
          }
          const signature = body instanceof FormData ? JSON.stringify(Array.from(body.entries()).map(([k,v]) => [k, typeof v === 'string' ? v : [v.name,v.size,v.lastModified]])) : body;
          if (priorBody && priorBody !== signature) key = crypto.randomUUID();
          priorBody = signature;
          await api(path, {method:'POST', body, headers:{'Idempotency-Key':key}});
          showDetail(await api(`requests/${job.id}/`)); toast('Saved.');
        } catch (error) {
          const target = form.querySelector('.collaborationError'); target.hidden = false; target.textContent = error.message;
        } finally { if (button.isConnected) button.disabled = false; }
      };
    }
  }
  async function notificationCentre(before) {
    try {
      const data = await api('notifications/' + (before ? '?before=' + before : ''));
      modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><h1>Operations notifications</h1><p>${data.unread_count} unread · Local email testing mode</p>${data.items.map(item => `<div class="activity"><strong>${esc(item.event)}${item.read ? '' : ' · Unread'}</strong><p>${esc(item.agency)} · ${esc(item.property)}<br>${esc(item.job_number)}</p><small>${esc(date(item.at))}</small><div class="actions"><button class="secondary notificationOpen" data-id="${item.id}" data-target="${item.job_id}">Open job</button><button class="secondary notificationRead" data-id="${item.id}" data-read="${!item.read}">${item.read ? 'Mark unread' : 'Mark read'}</button></div></div>`).join('') || '<p>No notifications yet.</p>'}${data.next ? `<button class="secondary" id="olderNotifications">Older notifications</button>` : ''}`;
      if (!modal.open) modal.showModal();
      if ($('#olderNotifications')) $('#olderNotifications').onclick = () => notificationCentre(data.next);
      modal.querySelectorAll('.notificationRead').forEach(button => { button.onclick = async () => { try { await api(`notifications/${button.dataset.id}/`, {method:'POST',body:JSON.stringify({read:button.dataset.read === 'true'})}); await notificationCentre(before); await notificationCount(); } catch (error) { toast(error.message); } }; });
      modal.querySelectorAll('.notificationOpen').forEach(button => { button.onclick = async () => { try { await api(`notifications/${button.dataset.id}/`, {method:'POST',body:JSON.stringify({read:true})}); showDetail(await api(`requests/${button.dataset.target}/`)); await notificationCount(); } catch (error) { toast(error.message); } }; });
    } catch (error) { toast(error.message); }
  }
  async function notificationCount() {
    if (context.user.role !== 'superadmin') return;
    try { const data = await api('notifications/'); if ($('#notifications')) $('#notifications').textContent = `🔔 Notifications (${data.unread_count})`; } catch (error) { toast(error.message); }
  }
  function showDetail(job) {
    const generation = ++detailGeneration;
    selected = job;
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">${esc(job.reference)} · ${esc(job.category)}</span><p><small>${job.official_job_reference ? `Original request ${esc(job.request_reference)}` : 'Repair request · an official SV number is issued after authorised call-out or quotation approval.'}</small></p><h1 class="job-property-address">${esc(job.property.address)}</h1><p class="job-repair-title">${esc(job.title)}</p><div class="toolbar">${badge(job.status_label)} ${badge(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[job.urgency]||'Not set')}</div><p><b>${esc(job.property.name)}</b><br>${esc(job.property.address)}</p><div class="notice"><span class="eyebrow">AGENCY & PROPERTY MANAGER</span><h2 style="margin:10px 0">${esc(job.property.agency)}</h2><p><b>PM: ${esc(job.property.manager)}</b></p></div><p style="white-space:pre-wrap">${esc(job.description)}</p><div class="notice"><h2>Job attachments · ${job.attachments.length}</h2>${job.attachments.map(file => `<div class="file"><div>📄 ${esc(file.filename)}<br><small>${Math.ceil(file.size / 1024)} KB</small></div><a class="secondary" href="${esc(file.download_url)}" download>Download</a></div>`).join('') || '<p>No attachments yet.</p>'}</div>${!['completed','cancelled','closed'].includes(job.status) ? '<form id="attachmentForm"><label>Add shared photos or documents</label><input name="attachments" type="file" multiple required accept="image/jpeg,image/png,image/webp,application/pdf"><small>Up to 5 files at a time, 5 MB each; 10 per request. Files are shared with the tenant, authorised managers and Sevlink. Do not attach private/internal documents.</small><p id="attachmentError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Upload attachments</button></div></form>' : ''}${collaborationMarkup(job)}<div class="tabs"><button class="selected">Timeline</button></div><div id="jobcontent">${job.activity.map(e => `<div class="activity"><span class="dot"></span>${esc(e.type === 'job_submitted' ? 'Report submitted · Awaiting property manager review' : e.type === 'status_changed' ? ({reviewed:'Reviewed',in_progress:'In progress'}[e.details.status] || e.label) : e.label)}<small>${esc(e.actor)} · ${esc(date(e.at))}</small></div>`).join('')}</div>${job.allowed_statuses.length ? `<form id="statusForm"><label>Update status</label><select name="status" required>${job.allowed_statuses.map(s => `<option value="${s.value}">${esc(s.label)}</option>`).join('')}</select><p id="statusError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Save status</button></div></form>` : ''}`;
    if (!modal.open) modal.showModal();
    wireCollaboration(job);
    window.SevlinkWorkflowUI?.job(job,{api,context,modal,showDetail,toast});
    if(!job.workflow || job.workflow.compatibility)portalTools(job,generation);
    if ($('#attachmentForm')) $('#attachmentForm').onsubmit = async event => {
      event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
      try {
        await api(`requests/${job.id}/attachments/`, {method:'POST', body:new FormData(event.target)});
        showDetail(await api(`requests/${job.id}/`)); toast('Attachments saved.');
      } catch (error) {
        $('#attachmentError').hidden = false; $('#attachmentError').textContent = error.message;
      } finally { if (button.isConnected) button.disabled = false; }
    };
    if ($('#statusForm')) $('#statusForm').onsubmit = async event => {
      event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
      try {
        const updated = await api(`requests/${selected.id}/`, {method:'PATCH', body:JSON.stringify({status:new FormData(event.target).get('status'), version:selected.version})});
        showDetail(updated);
        try { await loadJobs(); render(); toast('Status saved.'); }
        catch { toast('Status saved. Refresh the list to see it.'); }
      } catch (error) {
        // Refresh the version/status after a conflict; do not silently retry the write.
        try { showDetail(await api(`requests/${selected.id}/`)); } catch { /* Keep visible error on the current dialog. */ }
        if ($('#statusError')) { $('#statusError').hidden = false; $('#statusError').textContent = error.message; } else toast(error.message);
      } finally { if (button.isConnected) button.disabled = false; }
    };
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.hasAttribute('data-close')) modal.close();
    if (button.dataset.view) { document.body.classList.remove('phone-menu-open'); const previousView=view;view = button.dataset.view;if(view==='requests'||previousView==='requests')await refresh(1);else render();window.scrollTo({top:0}); }
    if (button.dataset.category && context.can_report) reportForm(button.dataset.category);
    if(button.dataset.ack){try{await api('portal-acknowledge/',{method:'POST',body:JSON.stringify({key:button.dataset.ack})});render();}catch(error){toast(error.message);}}
    if(button.dataset.resolve){try{await api(`requests/${button.dataset.actionJob}/portal-actions/`,{method:'POST',body:JSON.stringify({resolve:Number(button.dataset.resolve)})});if(modal.open && selected?.id===button.dataset.actionJob)showDetail(await api(`requests/${selected.id}/`));render();}catch(error){toast(error.message);}}
    if (button.dataset.job) {
      try { showDetail(await api(`requests/${button.dataset.job}/`)); if(button.dataset.target==='appointment'){const d=await api('portal/calendar/?'+new URLSearchParams({week:button.dataset.appointmentDate?.slice(0,10) || customerWeek || new Date().toLocaleDateString('en-CA')}));const a=d.appointments.find(a=>String(a.id)===button.dataset.targetId);if(a)modal.insertAdjacentHTML('afterbegin',`<section class="notice"><h2>Appointment · ${esc(a.appointment_status)}</h2><p>${esc(date(a.starts_at))} – ${esc(date(a.ends_at))}</p></section>`);} else if(button.dataset.targetId){const item=modal.querySelector(`[data-record-id="${CSS.escape(button.dataset.targetId)}"], [data-invoice="${CSS.escape(button.dataset.targetId)}"], [data-quote="${CSS.escape(button.dataset.targetId)}"]`);item?.scrollIntoView({block:'center'});} } catch (error) { toast(error.message); }
    }
  });
  let regionPage = 1, regionFilters = {}, regionData, regionRequest = 0;
  const options = (items, value = '', label = 'name') => items.map(i => `<option value="${esc(i.id)}" ${String(i.id) === String(value) ? 'selected' : ''}>${esc(i[label])}</option>`).join('');
  function regionSelects(prefix, values = {}) {
    const cities = regionData.cities.filter(c => !values.province || String(c.province_id) === String(values.province));
    const suburbs = regionData.suburbs.filter(s => values.city && String(s.city_id) === String(values.city));
    return `<label>Province</label><select id="${prefix}Province"><option value="">All provinces</option>${options(regionData.provinces, values.province)}</select><label>City</label><select id="${prefix}City"><option value="">All cities</option>${options(cities, values.city)}</select><label>Suburb</label><select id="${prefix}Suburb"><option value="">All suburbs</option>${options(suburbs, values.suburb)}</select>`;
  }
  async function regionalWorkspace() {
    const requestNumber = ++regionRequest;
    try {
      const data = await api('operations/regions/?' + new URLSearchParams({...regionFilters, page:regionPage}));
      if (view !== 'regions' || requestNumber !== regionRequest) return;
      regionData = data;
      const label = p => [data.suburbs.find(s => s.id === p.suburb)?.name, data.cities.find(c => c.id === p.city)?.name, data.provinces.find(r => r.id === p.province)?.name].filter(Boolean).join(', ') || 'Location not mapped';
      app.innerHTML = heading('Service areas & assignments', 'Private Sevlink Operations · Gauteng, Cape Town and all South African provinces.') +
        `<div class="panel"><div class="filters">${regionSelects('regionFilter', regionFilters)}</div><form id="supplierFilters"><div class="filters"><input name="search" placeholder="Search subcontractor / contact" aria-label="Search subcontractors" value="${esc(regionFilters.search || '')}"><select name="trade" aria-label="Trade category"><option value="">All trades</option>${data.trade_options.map(t => `<option ${t === regionFilters.trade?'selected':''}>${esc(t)}</option>`).join('')}</select><select name="status" aria-label="Subcontractor status"><option value="">All supplier statuses</option>${['active','inactive','archived'].map(t => `<option ${t===regionFilters.status?'selected':''}>${t}</option>`).join('')}</select><button class="secondary" type="submit">Filter subcontractors</button></div></form><div class="actions"><button class="secondary" id="newSubcontractor">Add subcontractor</button><button class="secondary" id="newLocation">Add city or suburb</button><button class="secondary" id="supplierInvoiceLedger">Supplier invoices & payments</button></div></div>` +
        `<div class="panel" style="margin-top:26px"><h2>Compliance expiry alerts (${data.compliance_alerts.count})</h2>${data.compliance_alerts.items.map(d => `<p>${esc(d.name)} · ${esc(d.title)} · ${esc(d.state)} · ${esc(d.expires_on)} <button class="secondary" data-supplier="${d.subcontractor}">Review compliance</button></p>`).join('') || '<p>No recorded documents expired or due within 30 days. Missing documents are not verified compliance.</p>'}<h2>Assignment reviews</h2>${data.assignment_reviews.map(r => `<p>${esc(r.reference)} · ${esc(r.name)} · ${esc(r.reason)} <button class="secondary" data-supplier="${r.subcontractor}">Review assignment</button></p>`).join('') || '<p>No pending assignment review flags.</p>'}</div>` +
        `<div class="panel" style="margin-top:26px"><h2>Private subcontractors (${data.subcontractors.count})</h2><div class="tablewrap"><table><thead><tr><th>Name</th><th>Service areas</th><th></th></tr></thead><tbody>${data.subcontractors.results.map(c => `<tr><td>${esc(c.name)}${c.archived ? ' (archived)' : c.active ? '' : ' (inactive)'}</td><td>${esc([...c.provinces.map(id => data.provinces.find(x => x.id === id)?.name), ...c.cities.map(id => data.cities.find(x => x.id === id)?.name), ...c.suburbs.map(id => data.suburbs.find(x => x.id === id)?.name)].join(', '))}</td><td><button class="secondary" data-supplier="${c.id}">Profile & teams</button><button class="secondary" data-contractor="${c.id}">Edit coverage</button></td></tr>`).join('') || '<tr><td colspan="3">No subcontractors in this area.</td></tr>'}</tbody></table></div></div>` +
        `<div class="panel" style="margin-top:26px"><h2>Properties (${data.properties.count})</h2><div class="tablewrap"><table><thead><tr><th>Property / agency</th><th>Location</th><th></th></tr></thead><tbody>${data.properties.results.map(p => `<tr><td>${esc(p.name)} · ${esc(p.agency)}<small>${esc(p.address)}</small></td><td>${esc(label(p))}</td><td><button class="secondary" data-map-property="${p.id}">Map location</button></td></tr>`).join('') || '<tr><td colspan="3">No properties in this area.</td></tr>'}</tbody></table></div></div>` +
        `<div class="panel" style="margin-top:26px"><h2>Maintenance jobs (${data.jobs.count})</h2><div class="tablewrap"><table><thead><tr><th>Job / property</th><th>Location</th><th></th></tr></thead><tbody>${data.jobs.results.map(j => `<tr><td>${esc(j.title)}<small>${esc(j.reference)} · ${esc(j.property.name)} · ${esc(j.property.agency)}</small></td><td>${esc(label(j.property))}</td><td><button class="secondary" data-regional-job="${j.id}" ${j.assignment_ready===false?'disabled title="Authorisation milestone required"':''}>Private assignment</button></td></tr>`).join('') || '<tr><td colspan="3">No jobs in this area.</td></tr>'}</tbody></table></div><div class="toolbar"><button class="secondary" id="regionsPrevious" ${regionPage === 1 ? 'disabled' : ''}>← Previous</button><span>Page ${regionPage} · Up to 50 of each record type per page</span><button class="secondary" id="regionsNext" ${Math.max(data.jobs.count, data.properties.count, data.subcontractors.count) <= regionPage*50 ? 'disabled' : ''}>Next →</button></div></div>`;
      $('#supplierFilters').onsubmit = e => {e.preventDefault();regionFilters={...regionFilters,...Object.fromEntries(new FormData(e.target))};regionPage=1;regionalWorkspace();};
      const filterChange = () => { regionPage = 1; regionalWorkspace(); };
      $('#regionFilterProvince').onchange = e => { regionFilters = {...regionFilters,province:e.target.value,city:'',suburb:''}; filterChange(); };
      $('#regionFilterCity').onchange = e => { regionFilters = {...regionFilters,province:$('#regionFilterProvince').value, city:e.target.value,suburb:''}; filterChange(); };
      $('#regionFilterSuburb').onchange = e => { regionFilters.suburb = e.target.value; filterChange(); };
      $('#regionsPrevious').onclick = () => { regionPage--; regionalWorkspace(); };
      $('#regionsNext').onclick = () => { regionPage++; regionalWorkspace(); };
      app.querySelectorAll('[data-supplier]').forEach(b => b.onclick = () => supplierProfile(b.dataset.supplier));
      $('#newSubcontractor').onclick = () => contractorForm();
      $('#newLocation').onclick = () => locationForm();
      $('#supplierInvoiceLedger').onclick=()=>supplierInvoiceLedger();
      app.querySelectorAll('[data-contractor]').forEach(b => b.onclick = () => contractorForm(data.subcontractors.results.find(c => c.id === b.dataset.contractor)));
      app.querySelectorAll('[data-map-property]').forEach(b => b.onclick = () => mapProperty(data.properties.results.find(p => p.id === b.dataset.mapProperty)));
      app.querySelectorAll('[data-regional-job]').forEach(b => b.onclick = () => assignRegionalJob(b.dataset.regionalJob));
    } catch (error) { toast(error.message); }
  }
  function regionModal(title, body) {
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">PRIVATE SEVLINK OPERATIONS</span><h1>${title}</h1>${body}`;
    if (!modal.open) modal.showModal();
  }
  function contractorForm(item) {
    const select = (name, list) => `<label>${name} (multiple selections allowed)</label><select name="${name}" multiple size="5">${list.map(i => `<option value="${i.id}" ${item?.[name].includes(i.id) ? 'selected' : ''}>${esc(i.name)}</option>`).join('')}</select>`;
    regionModal('Subcontractor service areas', `<form id="regionContractor"><label>Name (Operations only)</label><input name="name" required maxlength="180" value="${esc(item?.name || '')}"><label><input name="active" type="checkbox" ${item?.active !== false ? 'checked' : ''}> Active</label><p>A province covers all its cities and suburbs; a city covers all its suburbs. Select individual suburbs for narrower coverage.</p>${select('provinces', regionData.provinces)}${select('cities', regionData.cities.map(c => ({...c, name:c.name + ', ' + regionData.provinces.find(p => p.id === c.province_id)?.name})))}${select('suburbs', regionData.suburbs.map(s => ({...s, name:s.name + ', ' + regionData.cities.find(c => c.id === s.city_id)?.name})))}<div class="actions"><button type="submit" class="primary">Save service areas</button></div></form>`);
    $('#regionContractor').onsubmit = async e => {
      e.preventDefault(); const form = e.target, button = form.querySelector('[type=submit]'); button.disabled = true;
      try { const f = new FormData(form); const body = {name:f.get('name'), active:form.elements.active.checked, ...Object.fromEntries(['provinces','cities','suburbs'].map(k => [k, f.getAll(k).map(Number)]))}; if (item) body.id = item.id;
        await api('operations/subcontractors/', {method:'POST', body:JSON.stringify(body)}); modal.close(); await regionalWorkspace(); toast('Service areas saved.');
      } catch (error) { toast(error.message); } finally { button.disabled = false; }
    };
  }
  function mapProperty(prop) {
    const values = {province:prop.province, city:prop.city, suburb:prop.suburb};
    const draw = () => {
      regionModal('Map property location', `<p>${esc(prop.name)} · ${esc(prop.address)}</p><form id="regionProperty">${regionSelects('mapping', values)}<p>Choose a city. Leave the suburb empty only if unknown; suburb-only contractors will then be excluded. Existing address text is preserved.</p><button type="submit" class="primary">Save location</button></form>`);
      $('#mappingProvince').onchange = e => { values.province = e.target.value; values.city = ''; values.suburb = ''; draw(); };
      $('#mappingCity').onchange = e => { values.city = e.target.value; values.suburb = ''; draw(); };
      $('#mappingSuburb').onchange = e => { values.suburb = e.target.value; };
      $('#regionProperty').onsubmit = async e => { e.preventDefault(); const button = e.target.querySelector('[type=submit]'); button.disabled = true;
        try { await api(`operations/properties/${prop.id}/location/`, {method:'POST', body:JSON.stringify({city:values.city, suburb:values.suburb || ''})}); modal.close(); await regionalWorkspace(); toast('Location saved.'); }
        catch (error) { toast(error.message); } finally { button.disabled = false; }
      };
    }; draw();
  }
  function locationForm() {
    regionModal('Add city or suburb', `<form id="regionLocation"><label>Location type</label><select name="kind"><option value="city">City</option><option value="suburb">Suburb</option></select><label>Name</label><input name="name" required maxlength="120"><label>Province (for a city)</label><select name="province">${options(regionData.provinces)}</select><label>City (for a suburb)</label><select name="city">${options(regionData.cities.map(c => ({...c,name:c.name+', '+regionData.provinces.find(p => p.id === c.province_id)?.name})))}</select><button type="submit" class="primary">Save location</button></form>`);
    $('#regionLocation').onsubmit = async e => { e.preventDefault(); const f = new FormData(e.target), kind = f.get('kind'), parent = kind === 'city' ? 'province' : 'city'; const button = e.target.querySelector('[type=submit]'); button.disabled = true;
      try { await api('operations/regions/', {method:'POST',body:JSON.stringify({kind, name:f.get('name'), [parent]:Number(f.get(parent))})}); modal.close(); await regionalWorkspace(); toast('Location added.'); }
      catch (error) { toast(error.message); } finally { button.disabled = false; }
    };
  }
  async function assignRegionalJob(id) {
    try {
      const data = await api(`operations/requests/${id}/assignments/`), key = crypto.randomUUID();
      regionModal('Private job assignment', `<p>${esc(data.reference)}</p>${data.location_required ? '<div class="notice">Map this property’s city and suburb before assigning.</div>' : `<form id="regionAssignment"><label>Active subcontractors covering this property</label><select name="subcontractor" required><option value="">Select subcontractor</option>${options(data.subcontractors)}</select><label>Team (required where teams are registered)</label><select name="team"><option value="">Unallocated / select a team</option></select><p>Location coverage is checked again when saved. Assignment records are private; they do not book a visit or change job status.</p><button type="submit" class="primary">Record assignment</button></form>`}<h2>Private assignment history (newest first)</h2>${data.history.map(a => `<p>${esc(a.name)} · ${esc(date(a.at))} · ${esc(a.team_name)}${a.reviews.length?' · REQUIRES OPERATIONS REVIEW':''}</p>`).join('') || '<p>No assignments recorded.</p>'}`);
      if ($('#regionAssignment')) {
        const form=$('#regionAssignment');form.elements.subcontractor.onchange=() => {const c=data.subcontractors.find(c=>c.id===form.elements.subcontractor.value);form.elements.team.innerHTML='<option value="">Unallocated / select a team</option>'+options(c?.teams || []);form.elements.team.required=!!c?.team_required;};
      }
      if ($('#regionAssignment')) $('#regionAssignment').onsubmit = async e => { e.preventDefault(); const button = e.target.querySelector('[type=submit]'); button.disabled = true;
        try { await api(`operations/requests/${id}/assignments/`, {method:'POST',body:JSON.stringify({subcontractor:new FormData(e.target).get('subcontractor'), team:new FormData(e.target).get('team') || '', version:data.version, submission_key:key})}); toast('Private assignment saved.'); await assignRegionalJob(id); }
        catch (error) { toast(error.message); } finally { button.disabled = false; }
      };
    } catch (error) { toast(error.message); }
  }

  const supplierPath = id => `operations/subcontractors/${id}/`;
  const field = (name,label,value='',type='text') => `<label>${label}</label><input name="${name}" type="${type}" value="${esc(value)}">`;
  async function supplierProfile(id) {
    try {
      const d = await api(supplierPath(id));
      const teams = d.teams.map(t => `<div class="panel supplierTeamCard" data-team-name="${esc(t.name.toLowerCase())}" data-active="${t.active}"><h2>${esc(t.name)} ${t.active ? '' : '(inactive)'}</h2><p>Working days: ${esc(t.working_days.map(n => ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][n]).join(', ') || 'Not set')} · ${esc(t.day_start)}–${esc(t.day_end)} (South Africa)</p><button class="secondary" data-team-edit="${t.id}">Edit team & availability</button><h3>Unavailable dates</h3>${t.unavailable.map(u => `<p>${esc(u.date)} · ${esc(u.reason)} <button class="secondary" data-remove-unavailable="${t.id}" data-date="${u.date}">Remove unavailable date</button></p>`).join('') || '<p>None recorded.</p>'}<form class="supplierUnavailable" data-team="${t.id}">${field('date','Unavailable date','','date')}${field('reason','Internal reason')}<button type="submit" class="secondary">Add unavailable date</button></form><h3>Appointments</h3>${t.appointments.map(a => `<p>${esc(date(a.starts_at))} – ${esc(date(a.ends_at))} ${a.cancelled_at ? '(cancelled)' : ''}</p>${a.cancelled_at ? '' : `<form class="supplierCancelAppointment" data-appointment="${a.id}">${field('reason','Reason for cancellation')}<button type="submit" class="secondary">Cancel appointment record</button></form>`}`).join('') || '<p>None recorded.</p>'}<form class="supplierAppointment"><label>Current job assignment</label><select name="assignment" required><option value="">Select assigned job</option>${d.assignments.filter(a => a.current && a.team_id === t.id).map(a => `<option value="${a.id}">${esc(a.title)} · ${esc(a.reference)}</option>`).join('')}</select>${field('starts_at','Appointment start (South African time)','','datetime-local')}${field('ends_at','Appointment end (South African time)','','datetime-local')}<button type="submit" class="secondary">Record appointment</button></form></div>`).join('');
      regionModal('Subcontractor profile', `<div id="supplierProfile"><p>Private Sevlink Operations · ${esc(d.name)}</p><button class="secondary" id="supplierReload">Refresh profile</button><form id="supplierProfileForm" data-version="${d.version}">${field('name','Company / trading name',d.name)}${field('contact_person','Contact person',d.contact_person)}${field('telephone','Telephone',d.telephone,'tel')}${field('whatsapp','WhatsApp',d.whatsapp,'tel')}${field('email','Email',d.email,'email')}<label>Status</label><select name="status">${['active','inactive','archived'].map(s => `<option ${s===d.status?'selected':''}>${s}</option>`).join('')}</select><label>Trade categories</label><select name="trades" multiple size="5">${d.trade_options.map(t => `<option ${d.trades.includes(t)?'selected':''}>${esc(t)}</option>`).join('')}</select><label>Specialisations</label><textarea name="specialisations" maxlength="2000">${esc(d.specialisations)}</textarea><label>Internal notes</label><textarea name="internal_notes" maxlength="4000">${esc(d.internal_notes)}</textarea><button type="submit" class="primary">Save private profile</button></form><h2>Coverage areas</h2><p>${esc([...d.provinces.map(pk => regionData.provinces.find(p => p.id===pk)?.name),...d.cities.map(pk => regionData.cities.find(c => c.id===pk)?.name),...d.suburbs.map(pk => regionData.suburbs.find(s => s.id===pk)?.name)].join(', '))}</p><button class="secondary" id="supplierCoverage">Edit service areas</button><h2>Compliance PDFs</h2><p>Private documents. Expiry alerts appear in Service areas; dates do not verify authenticity or compliance.</p>${d.documents.map(doc => `<p><a href="${esc(doc.url)}">${esc(doc.title)}</a> · ${esc(doc.kind)} · ${esc(doc.state)} ${doc.expires_on ? '· '+esc(doc.expires_on) : ''} ${doc.superseded ? '(replaced; historical PDF retained)' : ''}</p>`).join('') || '<p>No compliance documents uploaded.</p>'}<form id="supplierDocument"><label>Document type</label><select name="kind"><option value="cipc">CIPC registration</option><option value="insurance">Public liability insurance</option><option value="qualification">Trade qualification/certificate</option><option value="other">Other compliance</option></select>${field('title','Document title')}${field('expires_on','Expiry date (leave blank if not applicable)','','date')}<label>Replaces an existing document (optional, same type)</label><select name="previous"><option value="">New document</option>${d.documents.filter(doc => !doc.superseded).map(doc => `<option value="${doc.id}">${esc(doc.title)}</option>`).join('')}</select><label>Private PDF (maximum 5 MB)</label><input name="attachments" type="file" accept="application/pdf" required><button type="submit" class="secondary">Upload compliance PDF</button></form><h2>Private commercial agreements</h2>${d.agreements.map(a => `<p>${esc(date(a.created_at))} · Commission: ${esc(a.commission_percent || 'not specified')}% · ZAR ${esc(a.rate || 'not specified')} / ${esc(a.rate_basis)}<br>${esc(a.terms)}</p>`).join('') || '<p>No agreements recorded.</p>'}<form id="supplierAgreement">${field('commission_percent','Commission percentage (optional)','','number')}${field('rate','Negotiated rate in ZAR (optional)','','number')}<label>Rate basis</label><select name="rate_basis"><option value="hour">Per hour</option><option value="visit">Per visit</option><option value="fixed">Fixed</option></select><label>Agreement terms (internal)</label><textarea name="terms" required maxlength="4000"></textarea><p>New agreements preserve prior records. These terms do not calculate quotation or invoice totals.</p><button type="submit" class="secondary">Record agreement</button></form><h2>Private subcontractor invoices & manual payments</h2><p>Payments and bank details are managed outside Sevlink. Record only completed external payments here; no payment is initiated.</p>${d.invoices.map(i => supplierInvoiceCard(i)).join('') || '<p>No linked supplier invoices.</p>'}<form id="supplierInvoiceUpload"><label>Assigned maintenance job</label><select name="job" required><option value="">Select job</option>${options(d.invoice_jobs, '', 'title')}</select>${field('number','External subcontractor invoice number')}${field('amount','Invoice total (ZAR)','','number')}${field('due_date','Due date','','date')}<label>Externally prepared invoice PDF (maximum 5 MB)</label><input name="attachments" type="file" accept="application/pdf" required><button type="submit" class="secondary">Upload private supplier invoice</button></form><h2>Teams and scheduling preparation</h2><p>09:00–17:00 availability records; no calendar, dispatch or contractor acceptance is active.</p><button class="secondary" id="supplierNewTeam">Add team</button><div class="filters"><input id="supplierTeamSearch" aria-label="Search teams" placeholder="Search team name"><select id="supplierTeamStatus" aria-label="Filter teams"><option value="">All team statuses</option><option value="true">Active teams</option><option value="false">Inactive teams</option></select></div>${teams}<h2>Private assignment history</h2>${d.assignments.map(a => `<div class="comment"><p>${esc(a.title)} · ${esc(a.reference)} · ${esc(a.team)} · ${esc(date(a.at))} ${a.current ? '(current allocation)' : '(historical)'}</p>${a.reviews.map(r => `<form class="supplierReview" data-review="${r.id}"><p>REQUIRES OPERATIONS REVIEW: ${esc(r.reason)}</p>${field('reason','Review outcome / reconciliation reason')}<button type="submit" class="secondary">Acknowledge review</button></form>`).join('')}</div>`).join('') || '<p>No assignments.</p>'}<h2>Private activity history</h2>${d.activity.map(a => `<p>${esc(date(a.at))} · ${esc(a.action)} · user ${esc(a.actor)}</p>`).join('')}</div>`);
      $('#supplierReload').onclick = () => supplierProfile(id);
      $('#supplierCoverage').onclick = () => contractorForm(d);
      $('#supplierNewTeam').onclick = () => supplierTeamForm(id);
      const filterTeams=() => modal.querySelectorAll('.supplierTeamCard').forEach(card => {card.hidden=!card.dataset.teamName.includes($('#supplierTeamSearch').value.toLowerCase()) || (!!$('#supplierTeamStatus').value && card.dataset.active!==$('#supplierTeamStatus').value);});
      $('#supplierTeamSearch').oninput=filterTeams;$('#supplierTeamStatus').onchange=filterTeams;
      modal.querySelectorAll('[data-team-edit]').forEach(b => b.onclick = () => supplierTeamForm(id,d.teams.find(t => t.id===b.dataset.teamEdit)));
      const wire = (form,path,body) => { if (!form) return; form.onsubmit = async e => { e.preventDefault(); const button=form.querySelector('[type=submit]');button.disabled=true;
        try { await api(path,{method:'POST',body:body(form)}); await supplierProfile(id); toast('Private record saved.'); }
        catch (error) { toast(error.message); } finally { button.disabled=false; }
      }; };
      wire($('#supplierProfileForm'),supplierPath(id),form => {const f=new FormData(form);return JSON.stringify({...Object.fromEntries(f),trades:f.getAll('trades'),version:d.version});});
      for (const input of modal.querySelectorAll('#supplierAgreement input[type=number]')) {input.step='0.01';input.min='0';}
      const documentKey=crypto.randomUUID(),agreementKey=crypto.randomUUID();
      wire($('#supplierDocument'),supplierPath(id)+'documents/',form => {const f=new FormData(form);f.set('submission_key',documentKey);return f;});
      wire($('#supplierAgreement'),supplierPath(id)+'agreements/',form => JSON.stringify({...Object.fromEntries(new FormData(form)),submission_key:agreementKey}));
      modal.querySelectorAll('.supplierUnavailable').forEach(form => wire(form,supplierPath(id)+`teams/${form.dataset.team}/unavailable/`,f => JSON.stringify(Object.fromEntries(new FormData(f)))));
      modal.querySelectorAll('[data-remove-unavailable]').forEach(b => b.onclick = async () => {try {await api(supplierPath(id)+`teams/${b.dataset.removeUnavailable}/unavailable/`,{method:'POST',body:JSON.stringify({date:b.dataset.date,remove:true})});await supplierProfile(id);}catch(error){toast(error.message);}});
      modal.querySelectorAll('.supplierAppointment').forEach(form => wire(form,supplierPath(id)+'appointments/',f => {const b=Object.fromEntries(new FormData(f));return JSON.stringify({assignment:Number(b.assignment),starts_at:b.starts_at+'+02:00',ends_at:b.ends_at+'+02:00'});}));
      modal.querySelectorAll('.supplierCancelAppointment').forEach(form => wire(form,supplierPath(id)+'appointments/',f => JSON.stringify({cancel:Number(f.dataset.appointment),reason:new FormData(f).get('reason')})));
      modal.querySelectorAll('.supplierReview').forEach(form => wire(form,`operations/assignment-reviews/${form.dataset.review}/`,f => JSON.stringify(Object.fromEntries(new FormData(f)))));
      const invoiceKey=crypto.randomUUID();
      $('#supplierInvoiceUpload [name=amount]').step='0.01';
      $('#supplierInvoiceUpload').onsubmit=async e=>{e.preventDefault();const form=e.target,button=form.querySelector('[type=submit]');button.disabled=true;
        try {const body=new FormData(form),job=body.get('job');body.delete('job');body.set('subcontractor',id);await api(`requests/${job}/invoices/`,{method:'POST',body,headers:{'Idempotency-Key':invoiceKey}});await supplierProfile(id);toast('Private invoice saved.');}
        catch(error){toast(error.message);}finally{button.disabled=false;}
      };
      wireSupplierPayments(()=>supplierProfile(id));
    } catch(error) {toast(error.message);}
  }
  function supplierInvoiceCard(i) {
    const payable=i.document_status==='active' && !i.reconciliation_required && Number(i.outstanding)>0;
    return `<div class="panel"><h3>${esc(i.number)} · ${esc(i.supplier_name || '')}</h3><p>ZAR ${esc(i.amount)} · Due ${esc(i.due_date)} · ${esc(i.document_status)} / ${esc(i.payment_status)} · Net paid ${esc(i.net_paid_amount)} · Outstanding ${esc(i.outstanding)}</p><a href="${esc(i.document.download_url)}">Download private invoice PDF</a>${context.user.role==='superadmin'?`<button class="secondary" data-job="${i.job}">Open job / financial history</button>`:''}${i.payments.map(p=>`<p>External payment: ZAR ${esc(p.amount)} · ${esc(p.paid_on)} · Reference ${esc(p.reference)}</p>`).join('')}${payable?`<form class="supplierPayment" data-job="${i.job}" data-invoice="${i.id}" data-version="${i.version}">${field('amount','External payment amount (ZAR)','','number')}${field('paid_on','Payment date','','date')}${field('reference','External payment reference')}<button type="submit" class="secondary">Record payment / Mark as Paid</button></form>`:''}</div>`;
  }
  function wireSupplierPayments(refresh,root=modal) {
    root.querySelectorAll('.supplierPayment').forEach(form=>{const key=crypto.randomUUID();form.elements.amount.step='0.01';form.elements.reference.required=true;
      form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
        try {await api(`requests/${form.dataset.job}/invoices/${form.dataset.invoice}/payments/`,{method:'POST',body:JSON.stringify({...Object.fromEntries(new FormData(form)),version:Number(form.dataset.version)}),headers:{'Idempotency-Key':key}});await refresh();toast('External payment recorded.');}
        catch(error){toast(error.message);}finally{button.disabled=false;}
      };
    });
  }
  async function supplierInvoiceLedger(state='outstanding',page=1) {
    try {const d=await api('operations/supplier-invoices/?'+new URLSearchParams({state,page}));regionModal('Supplier invoices & manual payments',`<p>Operations only. External banking details and payments stay outside Sevlink.</p><label>Invoice filter</label><select id="supplierLedgerState">${['outstanding','all','paid','void'].map(s=>`<option ${s===state?'selected':''}>${s}</option>`).join('')}</select><p>${d.count} records · Page ${page}</p>${d.results.map(supplierInvoiceCard).join('') || '<p>No invoices match this filter.</p>'}<button class="secondary" id="supplierLedgerPrevious" ${page===1?'disabled':''}>Previous</button><button class="secondary" id="supplierLedgerNext" ${page*50>=d.count?'disabled':''}>Next</button>`);
      $('#supplierLedgerState').onchange=e=>supplierInvoiceLedger(e.target.value);
      $('#supplierLedgerPrevious').onclick=()=>supplierInvoiceLedger(state,page-1);$('#supplierLedgerNext').onclick=()=>supplierInvoiceLedger(state,page+1);
      wireSupplierPayments(()=>supplierInvoiceLedger(state,page));
    }catch(error){toast(error.message);}
  }
  function supplierTeamForm(id,t) {
    regionModal('Team availability', `<form id="supplierTeam">${field('name','Team name',t?.name || '')}<label><input name="active" type="checkbox" ${t?.active !== false?'checked':''}> Active team</label><label>Working days</label>${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((label,n) => `<label><input name="working_days" type="checkbox" value="${n}" ${t?.working_days.includes(n)?'checked':''}> ${label}</label>`).join('')}${field('day_start','Working day starts',t?.day_start || '09:00','time')}${field('day_end','Working day ends',t?.day_end || '17:00','time')}<p>Times use Africa/Johannesburg. Leave all working days unchecked until availability is confirmed.</p><button type="submit" class="primary">Save team</button></form>`);
    $('#supplierTeam').onsubmit = async e => {e.preventDefault();const form=e.target,button=form.querySelector('[type=submit]');button.disabled=true;const f=new FormData(form);
      try {await api(supplierPath(id)+'teams/',{method:'POST',body:JSON.stringify({...(t?{id:t.id}:{}),version:t?.version || 0,name:f.get('name'),active:form.elements.active.checked,working_days:f.getAll('working_days').map(Number),day_start:f.get('day_start'),day_end:f.get('day_end')})});await supplierProfile(id);toast('Team saved.');}
      catch(error){toast(error.message);}finally{button.disabled=false;}
    };
  }

  let calendarData, calendarWeek='', calendarFilters={}, calendarRequest=0, calendarDay=0;
  function calendarParams() {return new URLSearchParams({...calendarFilters,...(calendarWeek?{week:calendarWeek}:{})});}
  async function weeklyCalendar() {
    const ticket=++calendarRequest;
    try {
      const d=await api('operations/calendar/?'+calendarParams());
      if(view!=='calendar' || ticket!==calendarRequest)return;
      calendarData=d;calendarWeek=d.week_start;
      const hours='<div class="week-hours"><span>09:00</span><span>11:00</span><span>13:00</span><span>15:00</span><span>17:00</span></div>';
      const dayCell=(t,day,n)=>{
        const items=d.appointments.filter(a=>a.team===t.id && a.date===day).sort((a,b)=>a.starts_at.localeCompare(b.starts_at));
        const ends=[];const laid=items.map(a=>{let lane=ends.findIndex(end=>end<=a.starts_at);if(lane<0)lane=ends.length;ends[lane]=a.ends_at;return {...a,lane};});
        const available=t.working_days.includes(n) && !t.unavailable.includes(day) && t.active;
        return `<div data-cal-day="${n}" class="${n!==calendarDay?'mobile-hidden':''}">${hours}<div class="week-track" style="height:${Math.max(1,ends.length)*76}px"><button class="week-empty" data-cal-new="${t.id}" data-date="${day}" aria-label="Schedule ${esc(t.name)} on ${day}">${items.length?'':available?'No bookings · schedule':'Unavailable / working days not set'}</button>${laid.map(a=>`<button class="week-booking ${a.override?'has-override':''}" data-appointment="${a.id}" data-left="${a.left_percent}" data-width="${a.width_percent}" style="left:${a.left_percent}%;width:${a.width_percent}%;top:${a.lane*76}px" title="${esc(a.reference+' · '+a.start+'–'+a.end+' · '+a.property+' · '+a.status_label)}"><b>${esc(a.start)}–${esc(a.end)}</b><small>${esc(a.reference)}</small><small>${esc(a.property)}</small><small>${esc(a.status_label)}${a.override?' · exception':''}</small></button>`).join('')}</div></div>`;
      };
      app.innerHTML=heading('Weekly Operations calendar','Monday to Sunday · 09:00–17:00 · Africa/Johannesburg · private staff scheduling')+`<div class="panel"><div class="calendar-tools"><button class="secondary" id="calendarPrevious">← Previous week</button><strong id="calendarWeek">${esc(d.week_start)} – ${esc(d.days[6])}</strong><button class="secondary" id="calendarNext">Next week →</button><button class="secondary" id="calendarRefresh">Refresh</button><button class="primary" id="calendarNew">Schedule a job</button></div><form id="calendarFilters"><div class="filters"><select name="province" aria-label="Calendar province"><option value="">All provinces</option>${options(d.provinces,calendarFilters.province)}</select><select name="city" aria-label="Calendar city"><option value="">All cities / Cape Town</option>${options(d.cities,calendarFilters.city)}</select><select name="trade" aria-label="Calendar trade"><option value="">All trades</option>${d.trades.map(t=>`<option ${t===calendarFilters.trade?'selected':''}>${esc(t)}</option>`).join('')}</select><select name="subcontractor" aria-label="Calendar subcontractor"><option value="">All subcontractors</option>${options(d.suppliers,calendarFilters.subcontractor)}</select><select name="team" aria-label="Calendar team"><option value="">All teams</option>${options(d.all_teams.map(t=>({...t,name:(d.suppliers.find(s=>s.id===t.subcontractor)?.name || '')+' · '+t.name})),calendarFilters.team)}</select><button class="secondary" type="submit">Filter calendar</button></div></form><div class="week-mobile-day"><label>Day</label><select id="calendarMobileDay">${d.days.map((day,n)=>`<option value="${n}" ${n===calendarDay?'selected':''}>${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][n]} ${day}</option>`).join('')}</select></div><div class="week-scroll"><div class="week-grid"><div class="week-heading">Subcontractor / team</div>${d.days.map((day,n)=>`<div class="week-heading ${n!==calendarDay?'mobile-hidden':''}" data-cal-day="${n}">${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][n]}<small style="display:block">${day}</small></div>`).join('')}</div>${d.teams.map(t=>`<div class="week-grid" data-calendar-team="${t.id}"><div class="week-team"><strong>${esc(t.supplier)}</strong><small>${esc(t.name)}</small><small>${t.active?'':'Inactive · '}${esc(t.day_start.slice(0,5))}–${esc(t.day_end.slice(0,5))}</small></div>${d.days.map((day,n)=>dayCell(t,day,n)).join('')}</div>`).join('') || '<p class="notice">No teams match. Register teams and confirmed availability in Service areas before scheduling.</p>'}</div><p>Booking widths represent their actual duration. Exceptions are outlined and audited. Location filters hide bookings outside that location; conflict checks still include every booking for the team.</p></div>`;
      $('#calendarPrevious').onclick=()=>{calendarWeek=d.previous;weeklyCalendar();};$('#calendarNext').onclick=()=>{calendarWeek=d.next;weeklyCalendar();};$('#calendarRefresh').onclick=weeklyCalendar;
      $('#calendarNew').onclick=()=>calendarForm();
      $('#calendarFilters [name=province]').onchange=e=>{$('#calendarFilters [name=city]').innerHTML='<option value="">All cities / Cape Town</option>'+options(d.cities.filter(c=>!e.target.value || String(c.province_id)===e.target.value));};
      $('#calendarFilters [name=subcontractor]').onchange=e=>{$('#calendarFilters [name=team]').innerHTML='<option value="">All teams</option>'+options(d.all_teams.filter(t=>!e.target.value || t.subcontractor===e.target.value));};
      $('#calendarFilters').onsubmit=e=>{e.preventDefault();calendarFilters=Object.fromEntries(new FormData(e.target));weeklyCalendar();};
      $('#calendarMobileDay').onchange=e=>{calendarDay=Number(e.target.value);app.querySelectorAll('[data-cal-day]').forEach(cell=>cell.classList.toggle('mobile-hidden',Number(cell.dataset.calDay)!==calendarDay));};
      app.querySelectorAll('[data-appointment]').forEach(b=>b.onclick=()=>calendarJob(d.appointments.find(a=>a.id===Number(b.dataset.appointment)).job,Number(b.dataset.appointment)));
      app.querySelectorAll('[data-cal-new]').forEach(b=>b.onclick=()=>calendarForm(null,null,{team:b.dataset.calNew,date:b.dataset.date}));
    }catch(error){toast(error.message);}
  }
  function calendarForm(existing=null,jobData=null,initial={}) {
    const d=calendarData,teamId=existing?.team || initial.team || '',supplier=existing?.subcontractor || d.all_teams.find(t=>t.id===teamId)?.subcontractor || '';
    const jobs=jobData?[{id:jobData.id,reference:jobData.reference,title:jobData.title,property:jobData.property,version:jobData.version},...d.jobs.filter(j=>j.id!==jobData.id)]:d.jobs;
    regionModal(existing?'Reschedule / reassign job':'Schedule an existing job',`<p>Private Operations scheduling. Changes do not automatically change the public job status.</p><label>Find an existing open job</label><input id="calendarJobSearch" placeholder="Job number, title or property"><button class="secondary" id="calendarFindJobs" type="button">Find jobs</button><form id="calendarBooking"><label>Maintenance job</label><select name="job" required ${existing?'disabled':''}>${jobs.map(j=>`<option value="${j.id}" data-version="${j.version}">${esc(j.title)} · ${esc(j.property)} · ${esc(j.reference)}</option>`).join('')}</select><small>Up to 100 search results. Search to find older jobs.</small><label>Subcontractor</label><select name="subcontractor" required><option value="">Select subcontractor</option>${options(d.suppliers,supplier)}</select><label>Team</label><select name="team" required></select><label><input name="customer_visible" type="checkbox" ${existing?.customer_visible?'checked':''}> Share confirmed appointment dates and times with the authorised PM and reporting tenant</label>${field('date','Appointment date',existing?.date || initial.date || d.week_start,'date')}${field('start','Start (South African time)',existing?.start || '09:00','time')}${field('end','End (South African time)',existing?.end || '10:00','time')}${existing?'<label>Reason for rescheduling / reassignment</label><textarea name="reason" required maxlength="500"></textarea>':''}${d.can_override?'<label>Super Admin overlap exception reason (only if authorising an overlap)</label><textarea name="override_reason" maxlength="1000"></textarea><small>This cannot override working days, unavailable dates, closed jobs or service coverage.</small>':''}<p id="calendarError" role="alert" hidden></p><button type="submit" class="primary">Save appointment</button></form>`);
    const form=$('#calendarBooking'),key=crypto.randomUUID();
    function teams(selected=''){form.elements.team.innerHTML='<option value="">Select active team</option>'+options(d.all_teams.filter(t=>t.subcontractor===form.elements.subcontractor.value),selected);}
    teams(teamId);form.elements.subcontractor.onchange=()=>teams();
    $('#calendarFindJobs').onclick=async()=>{try{const found=await api('operations/calendar/?'+new URLSearchParams({...calendarFilters,week:calendarWeek,job_search:$('#calendarJobSearch').value}));form.elements.job.innerHTML=found.jobs.map(j=>`<option value="${j.id}" data-version="${j.version}">${esc(j.title)} · ${esc(j.property)}</option>`).join('');}catch(error){toast(error.message);}};
    if(existing){$('#calendarJobSearch').disabled=true;$('#calendarFindJobs').disabled=true;}
    form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
      try{const f=new FormData(form);const data={job:form.elements.job.value,version:Number(form.elements.job.selectedOptions[0]?.dataset.version),subcontractor:f.get('subcontractor'),team:f.get('team'),starts_at:f.get('date')+'T'+f.get('start')+':00+02:00',ends_at:f.get('date')+'T'+f.get('end')+':00+02:00',submission_key:key,customer_visible:form.elements.customer_visible.checked};if(existing){data.appointment=existing.id;data.reason=f.get('reason');}if(f.get('override_reason'))data.override_reason=f.get('override_reason');
        await api('operations/calendar/save/',{method:'POST',body:JSON.stringify(data)});modal.close();await weeklyCalendar();toast('Appointment saved. Public status can be updated manually.');
      }catch(error){$('#calendarError').hidden=false;$('#calendarError').textContent=error.message;}finally{button.disabled=false;}
    };
  }
  async function calendarJob(jobId,appointmentId=null) {
    try{const d=await api(`operations/calendar/jobs/${jobId}/`),a=d.appointments.find(a=>a.id===appointmentId);
      regionModal(a?'Appointment details':'Maintenance job',`<h2>${esc(d.reference)}</h2><p>${esc(d.title)} · ${esc(d.property)} · ${esc(d.status_label)}</p>${a?`<p>${esc(a.supplier)} · ${esc(a.team_name)} · ${esc(a.date)} ${esc(a.start)}–${esc(a.end)} ${a.cancelled?'(cancelled)':''}</p>${a.override?`<p>Super Admin exception: ${esc(a.override.reason)} · user ${a.override.actor} · ${esc(date(a.override.at))}</p>`:''}<button class="secondary" id="calendarOpenJob">Open maintenance job</button>${context.user.role==='superadmin' && !a.customer_visible?'<button class="secondary" id="calendarShare">Share confirmed appointment with PM / tenant</button>':''}${a.customer_visible?'<p>Confirmed appointment dates/times shared with authorised participants.</p>':''}${!a.cancelled && !['completed','cancelled','closed'].includes(d.status)?'<button class="secondary" id="calendarReschedule">Reschedule / reassign</button>':''}${!a.cancelled?'<form id="calendarCancel"><label>Cancellation reason</label><textarea name="reason" required maxlength="500"></textarea><button type="submit" class="secondary">Cancel appointment</button></form>':''}`:''}<h2>Manual public progress update</h2><form id="calendarProgress"><label>New job status</label><select name="status">${d.allowed_statuses.map(s=>`<option value="${s.value}">${esc(s.label)}</option>`).join('')}</select><button class="secondary" type="submit" ${d.allowed_statuses.length?'':'disabled'}>Save public status</button></form>${context.user.role==='superadmin'?`<button class="secondary" data-job="${jobId}">Open full maintenance workspace record</button>`:''}<h2>Appointment history</h2>${d.appointments.map(item=>`<p>${esc(item.date)} ${esc(item.start)}–${esc(item.end)} · ${esc(item.supplier)} / ${esc(item.team_name)} · ${item.cancelled?'Cancelled: '+esc(item.cancellation_reason):'Active'} ${item.rescheduled_from?'· Replaces appointment '+item.rescheduled_from:''}${item.override?' · Audited overlap exception':''}</p>`).join('') || '<p>No appointments.</p>'}<h2>Public status history</h2>${d.history.map(h=>`<p>${esc(h.status)} · ${esc(date(h.at))}</p>`).join('')}`);
      if($('#calendarShare'))$('#calendarShare').onclick=async()=>{try{await api(`requests/${jobId}/portal-actions/`,{method:'POST',body:JSON.stringify({appointment:a.id,customer_visible:true})});await calendarJob(jobId,appointmentId);toast('Confirmed appointment shared; subcontractor details remain private.');}catch(error){toast(error.message);}};
      if($('#calendarOpenJob'))$('#calendarOpenJob').onclick=()=>calendarJob(jobId);
      if($('#calendarReschedule'))$('#calendarReschedule').onclick=()=>calendarForm(a,d);
      if($('#calendarCancel'))$('#calendarCancel').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;try{await api('operations/calendar/save/',{method:'POST',body:JSON.stringify({cancel:a.id,reason:new FormData(e.target).get('reason')})});await weeklyCalendar();await calendarJob(jobId,a.id);toast('Appointment cancelled; history retained.');}catch(error){toast(error.message);button.disabled=false;}};
      $('#calendarProgress').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;try{await api(`operations/calendar/jobs/${jobId}/progress/`,{method:'POST',body:JSON.stringify({status:new FormData(e.target).get('status'),version:d.version})});await weeklyCalendar();await calendarJob(jobId,appointmentId);toast('Public job status saved.');}catch(error){toast(error.message);button.disabled=false;}};
    }catch(error){toast(error.message);}
  }
  async function mondayPayments(period='monday',supplier='',page=1,extra={}) {
    try{const d=await api('operations/monday-payments/?'+new URLSearchParams({period,subcontractor:supplier,page,...extra}));if(view!=='monday')return;
      app.innerHTML=heading('Monday Payments Due','Private tracking of external manual payments. No bank transfers or automatic Monday payments.')+`<div class="stats"><div class="stat"><label>Outstanding in this filter</label><strong>R ${esc(d.outstanding_total)}</strong></div><div class="stat"><label>Overdue in this filter</label><strong>R ${esc(d.overdue_total)}</strong></div></div><div class="panel"><p>Upcoming Monday: <strong id="mondayCutoff">${esc(d.monday)}</strong> · Due today is not overdue until tomorrow.</p><form id="mondayFilters"><div class="filters"><select name="period" aria-label="Payments due filter">${[['upcoming','Upcoming'],['overdue','Overdue'],['paid','Paid Payments'],['all','All Payments'],['monday','Due on or before upcoming Monday']].map(([value,label])=>`<option value="${value}" ${value===period?'selected':''}>${label}</option>`).join('')}</select><select name="subcontractor" aria-label="Payments subcontractor"><option value="">All subcontractors</option>${options(d.suppliers,supplier)}</select><select name="agency"><option value="">All agencies</option>${options(d.agencies,extra.agency||'')}</select><select name="job"><option value="">All linked jobs</option>${options(d.jobs,extra.job||'')}</select><label>Due date<input name="due_date" type="date" value="${esc(extra.due_date||'')}"></label><label>Payment date<input name="payment_date" type="date" value="${esc(extra.payment_date||'')}"></label><select name="document_status"><option value="">All invoice statuses</option><option value="active" ${extra.document_status==='active'?'selected':''}>Active</option><option value="void" ${extra.document_status==='void'?'selected':''}>Void / corrected history</option></select><select name="invoice_status"><option value="">All payment states</option>${['unpaid','partially_paid','paid','refunded'].map(s=>`<option ${extra.invoice_status===s?'selected':''}>${s}</option>`).join('')}</select><label>Invoice amount (ZAR)<input name="amount" type="number" min="0.01" step="0.01" value="${esc(extra.amount||'')}"></label><button type="submit" class="secondary">Review payments</button></div></form><p>${d.count} outstanding invoices · Page ${page}</p><div id="mondayInvoices">${d.results.map(i=>`<div>${i.overdue?'<strong class="notice">Overdue invoice</strong>':''}${i.attention?'<p class="notice">Reconciliation hold — manual attention required.</p>':''}<p>Job ${esc(i.job_number)}</p>${supplierInvoiceCard(i)}</div>`).join('') || '<p>No outstanding invoices in this filter.</p>'}</div><button class="secondary" id="mondayPrevious" ${page===1?'disabled':''}>Previous</button><button class="secondary" id="mondayNext" ${page*50>=d.count?'disabled':''}>Next</button></div>`;
      $('#mondayFilters').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);const filters=Object.fromEntries(f);delete filters.period;delete filters.subcontractor;mondayPayments(f.get('period'),f.get('subcontractor'),1,filters);};$('#mondayPrevious').onclick=()=>mondayPayments(period,supplier,page-1,extra);$('#mondayNext').onclick=()=>mondayPayments(period,supplier,page+1,extra);
      wireSupplierPayments(()=>mondayPayments(period,supplier,page,extra),app);
    }catch(error){toast(error.message);}
  }

  async function portalTools(job,generation) {
    try {const data=await api(`requests/${job.id}/portal-actions/`);if(generation!==detailGeneration || selected?.id!==job.id || !modal.open)return;
      const actions=data.actions.filter(a=>!a.resolved);
      if(!actions.length)return;
      const target=modal.querySelector('[data-tab-panel="overview"]') || modal;
      target.insertAdjacentHTML('beforeend',`<section class="panel" id="portalTools">${actions.map(a=>`<p>${esc(a.text)}</p><button class="secondary" data-resolve="${a.id}" data-action-job="${job.id}">Mark action completed</button>`).join('')}</section>`);
    }catch(error){if(selected?.id===job.id)toast(error.message);}
  }
  const customerRole = () => context && ['admin','pm','tenant'].includes(context.user.role);
  const money = value => 'R '+Number(value).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2});
  let customerWeek='', accountFilter='all', customerRequest=0;
  const jobButton = row => `<button class="secondary" data-job="${row.job}" data-target="${esc(row.target || '')}" data-target-id="${esc(row.target_id || '')}" data-appointment-date="${esc(row.appointment_date || row.starts_at || '')}">${row.target==='quotation'?'Open quotation':row.target==='invoice'?'Open invoice':row.target==='appointment'?'Open appointment':'Review job'} →</button>`;

  function attentionMarkup(items) {
    return `<section class="panel attention-panel" id="attention"><div class="panelhead"><h2>Needs Your Attention <small>(${items.length} actions)</small></h2><button class="secondary" id="attentionRefresh">Refresh</button></div><p>Saved actions for your authorised portfolio. Payments count only after Sevlink records them.</p><div class="attention-grid">${items.map(r=>`<article class="attention-card urgency-${r.priority}"><strong>${esc(r.action)}</strong><p>${esc(r.property)}</p><p>${esc(r.reference)} · ${esc(r.title)}</p><p>${esc(r.status_label)} ${r.amount?'· '+esc(money(r.amount)):''}</p>${r.deposit_received?'<p>50% deposit threshold received.</p>':''}${r.due_date?`<p>Due ${esc(r.due_date)}</p>`:''}${r.appointment_date?`<p>${esc(date(r.appointment_date))}</p>`:''}<div class="actions">${jobButton(r)}${r.acknowledge?`<button class="secondary" data-ack="${esc(r.key)}">Mark reviewed</button>`:''}${r.target==='action'?`<button class="secondary" data-resolve="${r.target_id}" data-action-job="${r.job}">Mark action completed</button>`:''}</div></article>`).join('') || '<p class="empty">You have no unresolved actions.</p>'}</div></section>`;
  }
  async function customerOverview() {
    const request=++customerRequest;
    list();
    if(context.user.role!=='tenant')window.SevlinkWorkflowUI?.stages({api,app,showDetail,toast,context});
    try {const data=await api('portal/attention/');if(view!=='overview' || request!==customerRequest)return;
      app.insertAdjacentHTML('afterbegin',attentionMarkup(data.items));
      $('#attentionRefresh').onclick=customerOverview;
    } catch(error){if(view==='overview' && request===customerRequest)app.insertAdjacentHTML('afterbegin',`<p role="alert">${esc(error.message)}</p>`);}
  }
  async function customerPage() {
    if(view==='updates'){window.SevlinkWorkflowUI?.inbox({api,app,showDetail,toast});return;}
    const active=view, request=++customerRequest;
    const section=({accounts:'accounts',quotes:'quotations',publicCalendar:'calendar',properties:'properties',tenants:'tenants',profile:'profile',updates:'updates',issues:'issues',websiteIssues:'operationsIssues'})[view];
    app.innerHTML=heading('Loading…','Reading your saved Django records.');
    try {
      const data=await api(section==='operationsIssues'?'operations/website-issues/':'portal/'+section+'/?'+new URLSearchParams(section==='accounts'?{filter:accountFilter}:section==='calendar'?{week:customerWeek || new Date().toLocaleDateString('en-CA',{timeZone:'Africa/Johannesburg'})}:{}));
      if(view!==active || request!==customerRequest)return;
      if(section==='accounts'){
        const filters=[['all','All invoices'],['unpaid','Unpaid'],['deposit','50% deposit received'],['partial','Partially paid'],['paid','Fully paid'],['overdue','Overdue'],['cancelled','Cancelled or credited']];
        app.innerHTML=heading('Accounts & Payments','Agency-facing Sevlink invoices. Payment recording is restricted to authorised Sevlink staff.')+`<section class="panel"><label>Invoice filter</label><select id="accountFilter">${filters.map(([value,label])=>`<option value="${value}" ${accountFilter===value?'selected':''}>${label}</option>`).join('')}</select><div class="stats"><div class="stat"><label>Outstanding · selected filter</label><strong>${esc(money(data.outstanding))}</strong></div><div class="stat"><label>Overdue · selected filter</label><strong>${esc(money(data.overdue))}</strong></div></div><div class="attention-grid">${data.invoices.map(r=>`<article class="attention-card"><h2>${esc(r.invoice.number)}</h2><p>${esc(r.property)} · ${esc(r.reference)}</p><p>${esc(r.title)} · ${esc(r.status_label)}</p><p>Total ${esc(money(r.invoice.amount))} · Confirmed net paid ${esc(money(r.invoice.net_paid_amount))}</p><p>Job deposit confirmed ${esc(money(r.job_deposit.received))} / ${esc(money(r.job_deposit.required))}${r.job_deposit.arrangement?' · Agreed scheduling arrangement':''}</p><p>Outstanding ${esc(money(r.invoice.outstanding))} · Due ${esc(r.invoice.due_date)} ${r.overdue?'· OVERDUE':''}</p><p>${esc(filters.find(f=>f[0]===r.finance_state)?.[1] || r.finance_state)}${r.invoice.reconciliation_required?' · Sevlink reconciliation hold':''}</p><p>${r.invoice.payments.map(p=>`${esc(p.paid_on)}: ${esc(money(p.amount))}`).join('<br>') || 'No confirmed payments recorded.'}</p><a href="${esc(r.invoice.document.download_url)}">Download invoice PDF</a>${jobButton({...r,target:'invoice',target_id:r.invoice.id})}</article>`).join('') || '<p>No invoices match this filter.</p>'}</div></section>`;
        $('#accountFilter').onchange=e=>{accountFilter=e.target.value;customerPage();};
      } else if(section==='calendar'){
        customerWeek=data.week;
        app.innerHTML=heading('Maintenance Calendar','Only appointment details explicitly shared by Sevlink are shown. South African time.')+`<div class="calendar-tools"><button class="secondary" id="customerPrevious">← Previous week</button><input type="date" id="customerWeek" aria-label="Calendar week" value="${data.week}"><button class="secondary" id="customerNext">Next week →</button></div><div class="customer-week">${data.days.map(day=>`<section class="panel"><h2>${esc(new Date(day+'T12:00:00+02:00').toLocaleDateString('en-ZA',{weekday:'long',day:'numeric',month:'short',timeZone:'Africa/Johannesburg'}))}</h2>${data.appointments.filter(a=>a.starts_at.slice(0,10)===day).map(a=>`<article class="attention-card"><strong>${esc(a.reference)} · ${esc(a.appointment_status)}</strong><p>${esc(a.property)} · ${esc(a.title)}</p><p>${esc(date(a.starts_at))} – ${esc(date(a.ends_at))}</p><p>${esc(a.status_label)}</p>${jobButton({...a,target:'appointment',target_id:a.id})}</article>`).join('') || '<p>No shared appointments.</p>'}</section>`).join('')}</div>`;
        $('#customerPrevious').onclick=()=>{customerWeek=data.previous;customerPage();};$('#customerNext').onclick=()=>{customerWeek=data.next;customerPage();};$('#customerWeek').onchange=e=>{customerWeek=e.target.value;customerPage();};
      } else if(section==='properties'){
        app.innerHTML=heading(context.user.role==='tenant'?'My Property':'Properties','Your authorised property records.')+(context.user.role!=='tenant'?'<a class="button secondary" href="/properties/new/">Add Property</a>':'')+`<div class="attention-grid">${data.properties.map(p=>`<article class="panel"><h2>${esc(p.address)}</h2><p>${esc(p.name)} · ${esc(p.agency)}</p><p>Property manager: ${esc(p.manager)}</p>${p.edit_url?`<a class="secondary" href="${esc(p.edit_url)}">Edit Property</a> <a class="secondary" href="${esc(p.invite_url)}">Link Tenant</a>`:''}</article>`).join('') || '<p>No active property links.</p>'}</div>`;
      } else if(section==='tenants'){
        app.innerHTML=heading('Tenants','Active tenancies in your authorised portfolio.')+`<div class="attention-grid">${data.tenants.map(t=>`<article class="panel"><h2>${esc(t.name)}</h2><p>${esc(t.property)}</p><p>${esc(t.email)} · ${esc(t.phone)}</p><p>${t.linked?'Account linked':'Invitation pending'}</p></article>`).join('') || '<p>No active tenancies.</p>'}</div>`;
      } else if(section==='profile'){
        app.innerHTML=heading('Agency Profile','Your agency’s saved account details.')+`<section class="panel"><h2>${esc(data.name)}</h2><p>${esc(data.phone)}</p><p>${esc(data.area)}</p>${data.account_access_url?`<a class="secondary" href="${esc(data.account_access_url)}">Manage account access</a>`:''}</section>`;
      } else if(section==='quotations'){
        app.innerHTML=heading('Quotations','Externally prepared PDFs and recorded decisions.')+`<div class="attention-grid">${data.quotations.map(r=>`<article class="panel"><h2>${esc(r.quotation.reference || r.quotation.record_number)}</h2><p>${esc(r.property)} · ${esc(r.reference)}</p><p>${esc(r.quotation.status)} · Revision ${r.quotation.revision} · ${esc(money(r.quotation.amount))}</p>${jobButton({...r,target:'quotation',target_id:r.quotation.id})}</article>`).join('') || '<p>No shared quotations.</p>'}</div>`;
      } else if(section==='updates'){
        app.innerHTML=heading('Updates & Notifications','Saved public job activity for your authorised records.')+data.updates.map(r=>`<article class="panel"><h2>${esc(r.event.label)}</h2><p>${esc(r.reference)} · ${esc(r.property)} · ${esc(r.title)}</p><p>${esc(date(r.event.at))} · ${esc(r.event.actor)}</p>${jobButton(r)}${r.read?'<span>Read</span>':`<button class="secondary" data-ack="${esc(r.key)}">Mark read</button>`}</article>`).join('');
      } else if(section==='issues'){
        app.innerHTML=heading('Report Website Issue','Send a private website problem report to Sevlink Operations. For maintenance, use the repair workflow.')+`<section class="panel"><form id="websiteIssue"><label>Subject</label><input name="subject" required maxlength="180"><label>What went wrong?</label><textarea name="description" required maxlength="2500"></textarea><p>Do not include passwords, banking details or private access codes.</p><button class="primary" type="submit">Send website issue</button></form></section>`+data.issues.map(i=>`<article class="panel"><h2>${esc(i.subject)}</h2><p>${esc(i.id)} · ${esc(i.status)} · ${esc(date(i.created_at))}</p></article>`).join('');
        $('#websiteIssue').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{await api('portal-issues/',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});await customerPage();toast('Website issue saved for Sevlink Operations.');}catch(error){toast(error.message);button.disabled=false;}};
      } else if(section==='operationsIssues'){
        app.innerHTML=heading('Website Issues','Private customer website reports.')+data.issues.map(i=>`<article class="panel"><h2>${esc(i.subject)}</h2><p>${esc(i.agency)} · ${esc(i.status)} · ${esc(date(i.created_at))}</p><p>${esc(i.description)}</p></article>`).join('');
      }
    }catch(error){if(view===active && request===customerRequest)app.innerHTML=`<p class="notice" role="alert">${esc(error.message)}</p>`;}
  }

  async function start() {
    app.innerHTML = '<div class="notice" role="status">Loading your maintenance workspace…</div>';
    try {
      context = await api('context/'); await loadJobs(); render();
      const linkedJob = new URLSearchParams(location.search).get('job');
      if (linkedJob && /^[0-9a-f-]{36}$/i.test(linkedJob)) {
        try { showDetail(await api(`requests/${linkedJob}/`)); } catch (error) { toast(error.message); }
      }
    }
    catch (error) {
      app.innerHTML = `<div class="notice" role="alert">${esc(error.message)}</div><button class="secondary" id="retry">Try again</button>`;
      $('#retry').onclick = start;
    }
  }
  modal.addEventListener('close',()=>{if(customerRole())render();});
  setInterval(()=>{if(customerRole() && !modal.open && ['overview','accounts','publicCalendar','updates'].includes(view))render();},60000);
  start();
})();
