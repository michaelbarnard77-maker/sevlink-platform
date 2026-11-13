/* Staff-only handover notes. No note text enters the shared job payload. */
window.SevlinkInternalNotes=(()=>{
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date=value=>value?new Date(value).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short',timeZone:'Africa/Johannesburg'}):'';
  function mount({panel,job,api,toast}){
    if(job.can_edit_internal_notes!==true)return;
    const root=document.createElement('section');root.className='panel internal-job-notes';root.setAttribute('aria-label','Sevlink internal notes');
    root.innerHTML='<h2>Sevlink internal notes</h2><p role="status">Loading private note…</p>';panel.append(root);
    const path=`requests/${job.id}/internal-note/`;let state;
    const heading=()=>'<div class="internal-note-heading"><h2>Sevlink internal notes</h2><span class="internal-note-private">Sevlink staff only</span></div><p class="internal-note-help">A shared handover note for your team. Keep the current position and next action up to date.</p>';
    const privacy='<p class="internal-note-privacy">Private to authorised Sevlink staff. Excluded from customer views, emails and completion PDFs.</p>';
    function read(){
      if(!root.isConnected)return;
      root.innerHTML=heading()+`<div class="internal-note-text">${state.text?esc(state.text):'<span class="muted">No internal note saved yet. Add the current position, anything outstanding and the next action.</span>'}</div><p class="internal-note-meta">${state.author?'Last updated by <strong>'+esc(state.author)+'</strong>'+(state.updated_at?' · '+esc(date(state.updated_at)):''):'No changes recorded yet.'}</p><div class="actions"><button class="primary" type="button" data-note-edit>${state.text?'Edit note':'Add internal note'}</button><button class="secondary" type="button" data-note-history ${state.history_count?'':'disabled'}>View history (${state.history_count})</button></div><div data-note-history-panel hidden></div>`+privacy;
      root.querySelector('[data-note-edit]').onclick=edit;
      root.querySelector('[data-note-history]').onclick=()=>{const slot=root.querySelector('[data-note-history-panel]');if(!slot.hidden)slot.hidden=true;else history(1);};
    }
    function edit(){
      const version=state.version;let key=crypto.randomUUID(),lastBody='';
      root.innerHTML=heading()+`<form class="internal-note-form"><label for="internal-note-${esc(job.id)}">Update the current note</label><textarea id="internal-note-${esc(job.id)}" name="text" maxlength="6000" rows="9" placeholder="Current position\n\nOutstanding\n\nNext action">${esc(state.text)}</textarea><p class="internal-note-help">Edit this same note as the job progresses. Each save keeps a previous version in the history.</p><p class="internal-note-error" role="alert" hidden></p><div class="actions"><button class="primary" type="submit">Save internal note</button><button class="secondary" type="button" data-note-cancel>Cancel</button></div></form>`+privacy;
      const form=root.querySelector('form'),input=form.elements.text,error=form.querySelector('[role=alert]'),cancel=form.querySelector('[data-note-cancel]');
      input.focus();cancel.onclick=read;
      form.onsubmit=async event=>{
        event.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;cancel.disabled=true;error.hidden=true;
        const body=JSON.stringify({text:input.value,version});if(lastBody&&lastBody!==body)key=crypto.randomUUID();lastBody=body;
        try{
          const saved=await api(path,{method:'POST',body,headers:{'Idempotency-Key':key}});
          if(!root.isConnected)return;state=saved;form.removeAttribute('data-live-dirty');read();toast('Internal note saved. Job stage unchanged.');
        }catch(problem){if(root.isConnected){error.textContent=problem.message;error.hidden=false;}}
        finally{if(button.isConnected){button.disabled=false;cancel.disabled=false;}}
      };
    }
    async function history(page){
      const slot=root.querySelector('[data-note-history-panel]');if(!slot)return;
      slot.hidden=false;slot.innerHTML='<p role="status">Loading previous versions…</p>';
      try{
        const data=await api(path+'?history=1&page='+page);if(!slot.isConnected)return;
        slot.innerHTML='<h3>Previous versions</h3>'+data.history.map(item=>`<article class="internal-note-history-entry"><strong>${esc(item.author)}${item.updated_at?' · '+esc(date(item.updated_at)):''}</strong><div class="internal-note-text">${esc(item.text)||'<span class="muted">Note cleared.</span>'}</div></article>`).join('')+(!data.history.length?'<p>No previous versions.</p>':'')+`<div class="actions"><button class="secondary" type="button" data-history-prev ${page===1?'disabled':''}>← Previous</button><span>Page ${page}</span><button class="secondary" type="button" data-history-next ${data.has_next?'':'disabled'}>Next →</button></div>`;
        slot.querySelector('[data-history-prev]').onclick=()=>history(page-1);slot.querySelector('[data-history-next]').onclick=()=>history(page+1);
      }catch(problem){if(slot.isConnected)slot.innerHTML='<p role="alert">'+esc(problem.message)+'</p>';}
    }
    api(path).then(data=>{state=data;read();}).catch(problem=>{if(root.isConnected)root.innerHTML=heading()+'<p role="alert">'+esc(problem.message)+'</p><p>Reopen the job to try again.</p>'+privacy;});
    return root;
  }
  return {mount};
})();
