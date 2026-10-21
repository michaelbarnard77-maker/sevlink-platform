/* Authenticated adapter for the existing portal shell. No demo state or role switching. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date = value => new Date(value).toLocaleString('en-ZA', {dateStyle:'medium', timeStyle:'short'});
  const badge = value => `<span class="badge ${esc(value.split(' ')[0])}">${esc(value)}</span>`;
  const app = $('#app'), modal = $('#modal');
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
  async function loadJobs() {
    const data = await api('requests/?page=' + page);
    jobs = data.results; total = data.count; next = data.next;
  }
  const heading = (title, sub) => `<div class="heading"><div><span class="eyebrow">${context.user.role === 'superadmin' ? 'SEVLINK OPERATIONS' : 'PROPERTY MAINTENANCE'}</span><h1>${title}</h1><p style="margin:0">${sub}</p></div></div>`;
  function shell() {
    const items = [['overview','◫','Overview'], ['requests','☷','Repair jobs'], ...(context.can_report ? [['report','＋','Report a repair']] : [])];
    $('#nav').innerHTML = items.map(([key, icon, label]) => `<button data-view="${key}" class="${view === key ? 'active' : ''}">${icon} &nbsp; ${label}</button>`).join('') + '<a class="secondary" href="/">Account & properties</a>';
    $('.profile').innerHTML = `<span class="demo">SIGNED IN</span><span class="name">${esc(context.user.name)}<br><small>${esc({superadmin:'Sevlink Super Admin',admin:'Agency administrator',pm:'Property manager',tenant:'Tenant'}[context.user.role])}</small></span>${context.user.role === 'superadmin' ? '<button class="secondary" id="notifications" aria-label="Operations notifications">🔔 Notifications</button>' : ''}<button class="secondary" id="logout">Sign out</button>`;
    if ($('#notifications')) { $('#notifications').onclick = () => notificationCentre(); notificationCount(); }
    $('#logout').onclick = async () => {
      try {
        const response = await fetch('/logout/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}});
        if (!response.ok) throw Error('Sign out failed. Please try again.');
        location.assign('/login/');
      } catch (error) { toast(error.message); }
    };
    $('#breadcrumb').textContent = view === 'report' ? 'Report a repair' : view === 'requests' ? 'Repair jobs' : 'Overview';
    if (!$('#phoneBar')) {
      document.body.insertAdjacentHTML('beforeend', '<div id="phoneBar"></div><nav id="phoneNav" aria-label="Phone navigation"></nav><button id="phoneShade" aria-label="Close navigation menu"></button>');
    }
    $('#phoneBar').innerHTML = '<a class="phone-brand" href="/maintenance/">SEVLINK<span>PROPERTY MAINTENANCE</span></a><button id="phoneMenuButton" aria-label="Open navigation menu" aria-expanded="false">☰ Menu</button>';
    $('#phoneNav').innerHTML = items.map(([key, icon, label]) => `<button data-view="${key}" class="${view === key ? 'active' : ''}"><span aria-hidden="true">${icon}</span>${key === 'overview' ? 'Home' : key === 'requests' ? 'Jobs' : 'Report'}</button>`).join('');
    $('#phoneMenuButton').onclick = () => {
      const open = document.body.classList.toggle('phone-menu-open');
      $('#phoneMenuButton').setAttribute('aria-expanded', String(open));
    };
    $('#phoneShade').onclick = () => {
      document.body.classList.remove('phone-menu-open');
      $('#phoneMenuButton').setAttribute('aria-expanded', 'false');
    };

  }
  function list() {
    const title = context.can_report ? 'Your home. Your repairs.' : 'Every repair. One clear record.';
    app.innerHTML = heading(title, context.can_report ? 'Report a repair and follow updates from your property manager.' : 'Review maintenance requests and keep their status up to date.') +
      `<div class="stats">${[['Repair requests', total, 'Visible to your account'],['On this page', jobs.length, 'Up to 50 requests per page']].map(([label, number, help]) => `<div class="stat"><label>${label}</label><strong>${number}</strong><small>${help}</small></div>`).join('')}</div>` +
      '<div class="panel" style="margin-top:26px"><div class="panelhead"><h2>Repair jobs</h2><button class="secondary" id="refresh">Refresh</button></div><div class="filters"><input id="search" aria-label="Search requests on this page" placeholder="Search this page by repair or property"><select id="statusFilter" aria-label="Filter status"><option value="">All statuses</option>' + [...new Set(jobs.map(j => j.status_label))].map(s => `<option>${esc(s)}</option>`).join('') + '</select></div><div class="tablewrap"><table class="phone-cards repair-register-table"><thead><tr><th>PROPERTY / REPAIR</th><th>STATUS</th><th>REPORTED</th><th></th></tr></thead><tbody id="rows"></tbody></table></div><div class="toolbar" style="margin-top:18px"><button class="secondary" id="previous" ' + (page === 1 ? 'disabled' : '') + '>← Previous</button><span>Page ' + page + '</span><button class="secondary" id="next" ' + (next === null ? 'disabled' : '') + '>Next →</button></div></div>';
    function rows() {
      const query = $('#search').value.toLowerCase(), status = $('#statusFilter').value;
      $('#rows').innerHTML = jobs.filter(j => (!status || j.status_label === status) && `${j.reference} ${j.title} ${j.property.address} ${j.property.name} ${j.property.agency}`.toLowerCase().includes(query)).map(j =>
        `<tr><td data-label="PROPERTY / REPAIR"><strong>${esc(j.property.address)}</strong><small>${esc(j.property.name)} · ${esc(j.property.agency)}</small><p style="margin:7px 0 2px;color:var(--ink)">${esc(j.title)}</p><small>${esc(j.reference)} · ${esc(j.category)}</small></td><td data-label="STATUS">${badge(j.status_label)}</td><td data-label="REPORTED">${esc(date(j.created_at))}</td><td data-label="OPEN"><button class="secondary" data-job="${j.id}">Open job →</button></td></tr>`).join('') || '<tr><td colspan="4" class="empty">No repair jobs to show.</td></tr>';
    }
    $('#search').oninput = rows; $('#statusFilter').onchange = rows; rows();
    $('#refresh').onclick = () => refresh();
    $('#previous').onclick = () => refresh(page - 1);
    $('#next').onclick = () => refresh(next);
  }
  async function refresh(newPage = page) {
    const oldPage = page;
    try { page = newPage; await loadJobs(); render(); }
    catch (error) { page = oldPage; toast(error.message); }
  }
  const icons = {'Plumbing':'🚰','Electrical':'💡','Doors & locks':'🚪','Painting':'🖌','Tiling':'▦'};
  function reportLanding() {
    app.innerHTML = heading('What needs attention?', 'A few clear details help your property manager review the repair.') + '<div class="reportwrap"><div class="panel"><div class="step-label">01 / SELECT A REPAIR CATEGORY</div><div class="categorygrid">' + context.categories.map(c => `<button class="category illustrated" data-category="${esc(c)}"><span>${icons[c] || '⌂'}</span><b>${esc(c)}</b><small>Tell us what happened →</small></button>`).join('') + '</div><div class="notice">For immediate danger, use your established emergency contact. This portal does not dispatch emergency assistance.</div></div></div>';
  }
  function render() { shell(); if (view === 'report') reportLanding(); else list(); }
  function reportForm(category) {
    if (!context.properties.length) { toast('Your account needs an active property link. Contact your property manager.'); return; }
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">${esc(category)}</span><h1>Report a problem.</h1><form id="reportForm"><label>Your property</label><select name="property" required>${context.properties.map(p => `<option value="${p.id}">${esc(p.name)} · ${esc(p.address)}</option>`).join('')}</select><label>What is the problem?</label><input name="title" required maxlength="180"><label>Tell us what happened</label><textarea name="description" required rows="4" maxlength="2500" placeholder="Where is the issue, when did it start, and what can you see?"></textarea><label>Photos or documents (optional)</label><input name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><small>Up to 5 files, 5 MB each · JPEG, PNG, WebP or PDF.</small><div class="notice">Your report goes to your property manager for review. Attachments are shared with your property manager and Sevlink.</div><p id="formError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Send report to property manager</button></div></form>`;
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
    return `<label>External reference printed on PDF (SQ record ID is separate)</label><input name="reference" required maxlength="80" value="${esc(q.reference || '')}"><label>Recorded total (ZAR)</label><input name="amount" required type="number" min="0.01" max="9999999999.99" step="0.01" value="${esc(q.amount || '')}"><label>Title</label><input name="title" required maxlength="180" value="${esc(q.title || '')}"><label>Scope shared with the agency</label><textarea name="scope" maxlength="3000">${esc(q.scope || '')}</textarea>${upload ? '<label>Externally prepared quotation PDF</label><input name="attachments" type="file" required accept="application/pdf"><small>One PDF, up to 5 MB. Upload only the agency-facing Sevlink quotation. Keep subcontractor documents in Operations-only notes.</small>' : '<small>The uploaded PDF cannot be replaced. Upload a new revision to change the document.</small>'}`;
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
    return `<h2>Invoices</h2>${job.invoices.map(i => `<div class="card"><h2>${esc(i.number)}${i.visibility === 'internal' ? ' · Operations only' : ''}</h2><p>Sevlink record: ${esc(i.record_number || 'Legacy')} · PDF invoice number: ${esc(i.number)}</p><h2>ZAR ${esc(i.amount)}</h2><p>Due ${esc(i.due_date)} · Uploaded ${esc(date(i.uploaded_at))}</p>${badge(i.document_status)} ${badge(i.payment_status)}<p>Gross payments ZAR ${esc(i.paid_amount)} · Refunds ZAR ${esc(i.refunded_amount)} · Net paid ZAR ${esc(i.net_paid_amount)}<br>Outstanding ZAR ${esc(i.outstanding)} · Collectible ZAR ${esc(i.collectible)}</p>${i.previous_id ? '<p>Corrected replacement — original document retained in job history.</p>' : ''}${i.replacement_id ? '<p>Replacement invoice recorded; this original remains in history.</p>' : ''}<a class="secondary" href="${esc(i.document.download_url)}" download>Download invoice PDF</a>${i.credit_notes.map(n => `<p>External credit note ${esc(n.reference)} · ZAR ${esc(n.amount)} · <a href="${esc(n.document.download_url)}" download>Download credit note PDF</a></p>`).join('')}${i.payments.map(p => `<p>Manual payment: ZAR ${esc(p.amount)} · ${esc(p.paid_on)}${operations ? `<br><small>${esc(p.actor)} · ${esc(p.reference)} ${esc(p.note)}</small>` : ''}</p>${operations && Number(p.refundable)>0 ? refundForm(i,p) : ''}`).join('')}${i.refunds.map(r => `<p>Manual refund ZAR ${esc(r.amount)} · ${esc(r.refunded_on)}${operations ? `<br><small>${esc(r.actor)} · ${esc(r.reason)} · ${esc(r.reference)}</small>` : ''}</p>`).join('')}${i.reconciliation_required && !operations ? '<div class="notice">Payment collection is on reconciliation hold.</div>' : ''}${operations && i.document_status === 'active' && !i.reconciliation_required && i.payment_status !== 'paid' ? `<form class="invoicePayment" data-invoice="${i.id}" data-version="${i.version}"><label>Received payment amount (ZAR)</label><input name="amount" type="number" required min="0.01" max="${esc(i.outstanding)}" step="0.01"><label>Payment date</label><input name="paid_on" required type="date"><label>Payment reference (Operations only)</label><input name="reference" maxlength="180"><label>Private payment note</label><textarea name="note" maxlength="1000"></textarea>${errorMarkup}<button class="secondary" type="submit">Record manual payment</button></form>` : ''}${operations ? invoiceAdjustments(i) : ''}</div>`).join('') || '<p>No invoices yet.</p>'}${operations ? '<form id="invoiceForm"><h2>Upload invoice PDF</h2><label>Visibility — select carefully</label><select name="visibility"><option value="internal">Operations only — private subcontractor invoice</option><option value="shared">Agency-visible Sevlink invoice</option></select><label>External invoice number printed on PDF (SI record ID is separate)</label><input name="number" required maxlength="80"><label>Recorded total (ZAR)</label><input name="amount" type="number" required min="0.01" max="9999999999.99" step="0.01"><label>Due date</label><input name="due_date" required type="date"><label>Externally prepared invoice PDF</label><input name="attachments" type="file" required accept="application/pdf"><small>One PDF, up to 5 MB. Payments are recorded manually after upload.</small><p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Upload invoice PDF</button></form>' : ''}`;
  }
  function collaborationMarkup(job) {
    const canDecide = ['pm','admin'].includes(context.user.role), operations = context.user.role === 'superadmin', open = !['completed','cancelled'].includes(job.status);
    const quotations = context.user.role === 'tenant' ? '' : `<h2>Quotations</h2>${job.quotations.map(q => `<div class="card"><h2>${esc(q.title)} · Revision ${q.revision}</h2><p>Sevlink record: ${esc(q.record_number || 'Legacy')} · PDF reference: ${esc(q.reference)}</p>${q.status === 'approved' ? `<div class="notice">${q.approval_valid ? 'Current approval remains valid until a replacement is approved.' : 'Historical approval — replaced only after the linked amendment was approved.'}</div>` : ''}${q.amends_id ? `<p>Amends previously approved quotation ${esc(q.amends_record_number || q.amends_id)}. The original approval remains valid while this amendment is pending/rejected.</p><p>${esc(q.amendment_reason)}</p>` : ''}<p style="white-space:pre-wrap">${esc(q.scope)}</p><h2>ZAR ${esc(q.amount)}</h2>${badge(q.status)}${q.decision_reason ? `<p>${esc(q.decision_reason)}</p>` : ''}${q.document ? `<p>Uploaded ${esc(date(q.document.uploaded_at))}</p><p><a class="secondary" href="${esc(q.document.download_url)}" download>Download quotation PDF</a></p>` : '<p>Legacy quotation record — no uploaded PDF. No document is generated.</p>'}${q.history.map(h => `<small>${esc(h.action)} · ${esc(h.actor)} · ${esc(date(h.at))}${h.reason ? ' · ' + esc(h.reason) : ''}</small><br>`).join('')}${q.document && q.status === 'sent' && canDecide && open ? `<form class="quoteDecision" data-quote="${q.id}" data-version="${q.version}"><label>Decision</label><select name="status"><option value="approved">Approve</option><option value="rejected">Reject</option><option value="revision_requested">Request revision</option></select><label>Decision comment</label><textarea name="reason" required maxlength="1000"></textarea><p class="collaborationError" role="alert" hidden></p><button class="primary" type="submit">Save quotation decision</button></form>` : ''}${operations && q.document && q.status === 'draft' && open ? `<form class="quoteEdit" data-quote="${q.id}" data-version="${q.version}">${quoteFields(q,false)}<p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Save draft details</button></form><button class="primary quoteAction" data-quote="${q.id}" data-version="${q.version}" data-action="send">Send for approval</button>` : ''}${operations && q.approval_valid && !q.has_next_revision && open ? `<form class="quoteAmendment" data-quote="${q.id}" data-version="${q.version}"><h2>Request approved quotation amendment</h2>${quoteFields(q)}<label>Amendment reason shared with agency</label><textarea name="reason" required maxlength="1000"></textarea>${errorMarkup}<button class="secondary" type="submit">Upload quotation amendment</button></form>` : ''}${operations && ['sent','rejected','revision_requested'].includes(q.status) && open ? `<form class="quoteRevision" data-quote="${q.id}" data-version="${q.version}"><h2>Upload next revision</h2>${quoteFields(q)}<p class="collaborationError" role="alert" hidden></p><button class="secondary" type="submit">Upload revised quotation</button></form>` : ''}</div>`).join('') || '<p>No quotations yet.</p>'}`;
    const issue = operations && open ? `<form id="quoteForm"><h2>Upload quotation PDF</h2>${quoteFields()}<p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Save quotation draft</button></div></form>` : '';
    const canComment = context.user.role !== 'tenant' || job.tenant_comments_allowed;
    return `${quotations}${issue}${invoiceMarkup(job)}${operations ? `<p><button class="secondary" id="tenantConversation">${job.tenant_comments_allowed ? 'Disable' : 'Enable'} tenant conversation access</button></p>` : ''}<h2 style="margin-top:20px">Job conversation</h2>${job.comments.map(c => `<div class="comment"><b>${esc(c.actor)}${c.visibility === 'internal' ? ' · Operations only' : ''}</b><p style="white-space:pre-wrap">${esc(c.text)}</p><small>${esc(date(c.at))}</small>${c.attachments.map(a => `<p><a href="${esc(a.download_url)}" download>${esc(a.filename)}</a></p>`).join('')}</div>`).join('') || '<p>No comments yet.</p>'}${canComment ? `<form id="commentForm"><label>Comment</label><textarea name="text" required maxlength="2500" rows="3"></textarea>${operations ? '<label>Visibility</label><select name="visibility"><option value="shared">Shared with authorised job participants</option><option value="internal">Operations only — private note</option></select>' : ''}<label>Photos or documents (optional)</label><input name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Add comment</button></div></form>` : '<p>Tenant conversation access is disabled for this job.</p>'}`;
  }
  function wireCollaboration(job) {
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
    selected = job;
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">${esc(job.reference)} · ${esc(job.category)}</span><h1 class="job-property-address">${esc(job.property.address)}</h1><p class="job-repair-title">${esc(job.title)}</p><div class="toolbar">${badge(job.status_label)}</div><p><b>${esc(job.property.name)}</b><br>${esc(job.property.agency)}</p><div class="notice"><span class="eyebrow">PROPERTY MANAGER</span><p>${esc(job.property.manager)}</p></div><p style="white-space:pre-wrap">${esc(job.description)}</p><div class="notice"><h2>Job attachments · ${job.attachments.length}</h2>${job.attachments.map(file => `<div class="file"><div>📄 ${esc(file.filename)}<br><small>${Math.ceil(file.size / 1024)} KB</small></div><a class="secondary" href="${esc(file.download_url)}" download>Download</a></div>`).join('') || '<p>No attachments yet.</p>'}</div>${!['completed','cancelled'].includes(job.status) ? '<form id="attachmentForm"><label>Add shared photos or documents</label><input name="attachments" type="file" multiple required accept="image/jpeg,image/png,image/webp,application/pdf"><small>Up to 5 files at a time, 5 MB each; 10 per request. Files are shared with the tenant, authorised managers and Sevlink. Do not attach private/internal documents.</small><p id="attachmentError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Upload attachments</button></div></form>' : ''}${collaborationMarkup(job)}<div class="tabs"><button class="selected">Timeline</button></div><div id="jobcontent">${job.activity.map(e => `<div class="activity"><span class="dot"></span>${esc(e.type === 'job_submitted' ? 'Report submitted · Awaiting property manager review' : e.type === 'status_changed' ? ({reviewed:'Reviewed',in_progress:'In progress'}[e.details.status] || e.label) : e.label)}<small>${esc(e.actor)} · ${esc(date(e.at))}</small></div>`).join('')}</div>${job.allowed_statuses.length ? `<form id="statusForm"><label>Update status</label><select name="status" required>${job.allowed_statuses.map(s => `<option value="${s.value}">${esc(s.label)}</option>`).join('')}</select><p id="statusError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Save status</button></div></form>` : ''}`;
    if (!modal.open) modal.showModal();
    wireCollaboration(job);
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
    if (button.dataset.view) { document.body.classList.remove('phone-menu-open'); view = button.dataset.view; render(); window.scrollTo({top:0}); }
    if (button.dataset.category && context.can_report) reportForm(button.dataset.category);
    if (button.dataset.job) {
      try { showDetail(await api(`requests/${button.dataset.job}/`)); } catch (error) { toast(error.message); }
    }
  });
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
  start();
})();
