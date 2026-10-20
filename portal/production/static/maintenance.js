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
    $('.profile').innerHTML = `<span class="demo">SIGNED IN</span><span class="name">${esc(context.user.name)}<br><small>${esc({superadmin:'Sevlink Super Admin',admin:'Agency administrator',pm:'Property manager',tenant:'Tenant'}[context.user.role])}</small></span><button class="secondary" id="logout">Sign out</button>`;
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
  function collaborationMarkup(job) {
    const canDecide = ['pm','admin'].includes(context.user.role), operations = context.user.role === 'superadmin';
    const quotations = context.user.role === 'tenant' ? '' : `<h2>Quotations</h2>${job.quotations.map(q => `<div class="card"><h2>${esc(q.title)}</h2><p style="white-space:pre-wrap">${esc(q.scope)}</p><h2>ZAR ${esc(q.amount)}</h2>${badge(q.status)}${q.decision_reason ? `<p>${esc(q.decision_reason)}</p>` : ''}${q.status === 'pending' && canDecide && !['completed','cancelled'].includes(job.status) ? `<form class="quoteDecision" data-quote="${q.id}" data-version="${q.version}"><label>Decision</label><select name="status"><option value="approved">Approve</option><option value="rejected">Reject</option></select><label>Reason (required for rejection)</label><textarea name="reason" maxlength="1000"></textarea><p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Save quotation decision</button></div></form>` : ''}</div>`).join('') || '<p>No quotations yet.</p>'}`;
    const issue = operations && !['completed','cancelled'].includes(job.status) ? '<form id="quoteForm"><h2>Issue quotation</h2><label>Title</label><input name="title" required maxlength="180"><label>Scope shared with the agency</label><textarea name="scope" required maxlength="3000"></textarea><label>Total (ZAR)</label><input name="amount" required type="number" min="0.01" max="9999999999.99" step="0.01"><p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Issue quotation</button></div></form>' : '';
    return `${quotations}${issue}<h2 style="margin-top:20px">Shared comments</h2>${job.comments.map(c => `<div class="comment"><b>${esc(c.actor)}</b><p>${esc(c.text)}</p><small>${esc(date(c.at))}</small></div>`).join('') || '<p>No comments yet.</p>'}<form id="commentForm"><label>Comment shared with the tenant, agency and Sevlink</label><textarea name="text" required maxlength="2500" rows="3"></textarea><p class="collaborationError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Add comment</button></div></form>`;
  }
  function wireCollaboration(job) {
    const forms = [[$('#commentForm'), `requests/${job.id}/comments/`], [$('#quoteForm'), `requests/${job.id}/quotations/`],
      ...Array.from(modal.querySelectorAll('.quoteDecision')).map(form => [form, `requests/${job.id}/quotations/${form.dataset.quote}/decision/`])];
    for (const [form, path] of forms) {
      if (!form) continue;
      const key = crypto.randomUUID();
      form.onsubmit = async event => {
        event.preventDefault(); const button = form.querySelector('[type=submit]'); button.disabled = true;
        try {
          const data = Object.fromEntries(new FormData(form));
          if (form.dataset.version) data.version = Number(form.dataset.version);
          await api(path, {method:'POST', body:JSON.stringify(data), headers:{'Idempotency-Key':key}});
          showDetail(await api(`requests/${job.id}/`)); toast('Saved.');
        } catch (error) {
          const target = form.querySelector('.collaborationError'); target.hidden = false; target.textContent = error.message;
        } finally { if (button.isConnected) button.disabled = false; }
      };
    }
  }
  function showDetail(job) {
    selected = job;
    modal.innerHTML = `<button class="close" data-close aria-label="Close">×</button><span class="eyebrow">${esc(job.reference)} · ${esc(job.category)}</span><h1 class="job-property-address">${esc(job.property.address)}</h1><p class="job-repair-title">${esc(job.title)}</p><div class="toolbar">${badge(job.status_label)}</div><p><b>${esc(job.property.name)}</b><br>${esc(job.property.agency)}</p><div class="notice"><span class="eyebrow">PROPERTY MANAGER</span><p>${esc(job.property.manager)}</p></div><p style="white-space:pre-wrap">${esc(job.description)}</p><div class="notice"><h2>Shared attachments · ${job.attachments.length}</h2>${job.attachments.map(file => `<div class="file"><div>📄 ${esc(file.filename)}<br><small>${Math.ceil(file.size / 1024)} KB</small></div><a class="secondary" href="${esc(file.download_url)}" download>Download</a></div>`).join('') || '<p>No attachments yet.</p>'}</div>${!['completed','cancelled'].includes(job.status) ? '<form id="attachmentForm"><label>Add shared photos or documents</label><input name="attachments" type="file" multiple required accept="image/jpeg,image/png,image/webp,application/pdf"><small>Up to 5 files at a time, 5 MB each; 10 per request. Files are shared with the tenant, authorised managers and Sevlink. Do not attach private/internal documents.</small><p id="attachmentError" role="alert" hidden></p><div class="actions"><button class="secondary" type="submit">Upload attachments</button></div></form>' : ''}${collaborationMarkup(job)}<div class="tabs"><button class="selected">Timeline</button></div><div id="jobcontent">${job.activity.map(e => `<div class="activity"><span class="dot"></span>${esc(e.type === 'job_submitted' ? 'Report submitted · Awaiting property manager review' : e.type === 'status_changed' ? ({reviewed:'Reviewed',in_progress:'In progress'}[e.details.status] || e.label) : e.label)}<small>${esc(e.actor)} · ${esc(date(e.at))}</small></div>`).join('')}</div>${job.allowed_statuses.length ? `<form id="statusForm"><label>Update status</label><select name="status" required>${job.allowed_statuses.map(s => `<option value="${s.value}">${esc(s.label)}</option>`).join('')}</select><p id="statusError" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Save status</button></div></form>` : ''}`;
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
