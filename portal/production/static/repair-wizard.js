/* Presentation only: submits the existing multipart endpoint with its original idempotency key. */
window.SevlinkRepairWizard = (()=>{
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const renovation='Renovations & Refurbishments';
  function open({category,context,modal,api,toast,onSaved}){
    const direct=['pm','admin'].includes(context.user.role);
    if(!context.properties.length){toast('Your account needs an active property link. Contact your property manager.');return;}
    const categories=[...new Set([...context.categories,renovation])];
    let current=2,furthest=2,busy=false,readyToSend=false;
    const key=crypto.randomUUID(),objectURLs=[];
    const revoke=()=>{objectURLs.splice(0).forEach(url=>URL.revokeObjectURL(url));};
    modal.addEventListener('close',revoke,{once:true});
    const categoryTiles=categories.map(c=>`<button type="button" class="category illustrated" data-wizard-category="${esc(c)}" ${c===renovation?'disabled':''}><span>${window.SevlinkWorkflowUI.categoryIcon(c)}</span><b>${esc(c)}</b>${c===renovation?'<small>Use the PM / Admin renovations request</small>':''}</button>`).join('');
    modal.innerHTML=`<button class="close" data-close aria-label="Close">×</button><section class="repair-wizard"><span class="eyebrow">REPORT A REPAIR</span><h1>Tell us what needs attention.</h1><ol class="wizard-steps" aria-label="Repair reporting steps">${['Select Issue','Add Details','Access Information','Review & Submit'].map((s,i)=>`<li><button type="button" data-wizard-step="${i+1}">${i+1}. ${s}</button></li>`).join('')}</ol><form id="reportForm" novalidate><section data-wizard-panel="1" hidden><h2>Choose a category</h2><div class="categorygrid">${categoryTiles}</div></section><section data-wizard-panel="2"><h2>Repair details</h2><p class="wizard-selected-category"></p><label for="repairProperty">Your property</label><select id="repairProperty" name="property" required>${context.properties.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.address)}</option>`).join('')}</select><label for="repairTitle">What is the problem?</label><input id="repairTitle" name="title" required maxlength="180"><label for="repairDescription">Tell us what happened</label><textarea id="repairDescription" name="description" required rows="4" maxlength="2500" placeholder="Where is the issue, when did it start, and what can you see?"></textarea><label for="repairAttachments">Photos or documents (optional)</label><input id="repairAttachments" name="attachments" type="file" multiple accept="image/jpeg,image/png,image/webp,application/pdf"><small>JPEG, PNG, WebP or PDF · Up to 5 MB each and 25 MB total</small></section><section data-wizard-panel="3" hidden><h2>Access information${direct?' & authorisation':''}</h2>${direct?'<div class="wizard-fields"><div><label for="repairType">Work authorisation</label><select id="repairType" name="job_type"><option value="quoted">Request a quotation</option><option value="callout">Authorise a call-out</option></select></div><div><label for="repairUrgency">Official urgency</label><select id="repairUrgency" name="urgency"><option value="normal">Normal</option><option value="urgent">Urgent</option></select></div></div><div class="callout-limit" hidden><label for="repairLimit">Maximum authorised call-out total (ZAR, VAT-inclusive)</label><input id="repairLimit" name="limit" type="number" min="0.01" max="9999999999.99" step="0.01"></div><label for="repairAccess">Who arranges access?</label><select id="repairAccess" name="access_responsibility"><option value="pm">Property manager</option><option value="sevlink">Sevlink</option></select><p class="muted">If Sevlink arranges access, we use the linked tenant contact details under Properties. Please keep those details up to date.</p>':'<p>Your property manager decides urgency, work authorisation and who arranges access.</p>'}<label for="repairAccessNotes">Relevant access information</label><textarea id="repairAccessNotes" name="access_information" maxlength="2500" rows="4" placeholder="Access instructions, pets and anything relevant to attending the property."></textarea><div class="notice">A preferred attendance date is requested later when the job is eligible. This report does not book a visit.</div></section><section data-wizard-panel="4" class="wizard-review" hidden><h2>Review your report</h2><div id="repairReview"></div></section><div class="notice" style="margin-top:18px"><strong>Property emergency?</strong> Call Sevlink immediately on <a href="tel:+27810285034">081 028 5034</a>. Do not wait for an online response.</div><p id="formError" role="alert" hidden></p><div class="wizard-actions"><button class="secondary" type="button" id="repairBack">← Back</button><button class="primary" type="button" id="repairNext">Next →</button><button class="primary" type="submit" id="repairSubmit" hidden>${direct?'Send repair to Sevlink':'Send report to property manager'}</button></div></form></section>`;
    const form=modal.querySelector('#reportForm'),next=modal.querySelector('#repairNext'),submit=modal.querySelector('#repairSubmit'),error=modal.querySelector('#formError');
    window.SevlinkWorkflowUI.photoPicker(form.elements.attachments);
    if(direct){const toggle=()=>{const active=form.elements.job_type.value==='callout';modal.querySelector('.callout-limit').hidden=!active;form.elements.limit.disabled=!active;form.elements.limit.required=active;};form.elements.job_type.onchange=toggle;toggle();}
    function valid(step){
      const section=modal.querySelector(`[data-wizard-panel="${step}"]`);
      const bad=[...section.querySelectorAll('input,select,textarea')].find(el=>!el.disabled&&!el.checkValidity());
      if(bad){bad.reportValidity();bad.focus();return false;}return true;
    }
    function review(){
      revoke();const f=new FormData(form),prop=context.properties.find(p=>p.id===f.get('property'));
      const rows=[['Property',prop?.address||''],['Category',category],['Repair',f.get('title')],...(direct?[['Work type',form.elements.job_type.selectedOptions[0].textContent],['Urgency',form.elements.urgency.selectedOptions[0].textContent],...(f.get('limit')?[['Call-out spending limit','R '+f.get('limit')]]:[]),['Access arranged by',form.elements.access_responsibility.selectedOptions[0].textContent]]:[])];
      const files=[...form.elements.attachments.files];
      modal.querySelector('#repairReview').innerHTML=`<dl>${rows.map(([a,b])=>`<div><dt>${esc(a)}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl><h3>Repair details</h3><p>${esc(f.get('description'))}</p><h3>Access information</h3><p>${esc(f.get('access_information')||'No additional access information provided.')}</p><h3>Attachments (${files.length})</h3><ul>${files.map(file=>`<li>${esc(file.name)} · ${Math.ceil(file.size/1024)} KB</li>`).join('')||'<li>No attachments selected.</li>'}</ul><div class="wizard-photo-preview"></div><div class="notice">${direct?'Your repair goes directly to Sevlink. Quoted work still requires quotation approval before scheduling.':'Your report goes to your property manager for review. Attachments are shared with your property manager and Sevlink.'}</div>`;
      const preview=modal.querySelector('.wizard-photo-preview');files.filter(f=>f.type.startsWith('image/')).forEach(file=>{const img=document.createElement('img'),url=URL.createObjectURL(file);objectURLs.push(url);img.src=url;img.alt=file.name;preview.append(img);});
    }
    function show(step){
      current=step;furthest=Math.max(furthest,current);readyToSend=step===4;
      modal.querySelectorAll('[data-wizard-panel]').forEach(p=>p.hidden=Number(p.dataset.wizardPanel)!==step);
      modal.querySelectorAll('[data-wizard-step]').forEach(b=>{b.disabled=busy||Number(b.dataset.wizardStep)>furthest;b.setAttribute('aria-current',Number(b.dataset.wizardStep)===step?'step':'false');});
      modal.querySelector('.wizard-selected-category').textContent='Category: '+category;
      next.hidden=step===4;submit.hidden=step!==4;
      if(step===4)review();
      modal.scrollTop=0;const h=modal.querySelector(`[data-wizard-panel="${step}"] h2`);h.tabIndex=-1;h.focus({preventScroll:true});
    }
    modal.querySelectorAll('[data-wizard-step]').forEach(b=>b.onclick=()=>{const target=Number(b.dataset.wizardStep);if(target<current||valid(current))show(target);});
    modal.querySelectorAll('[data-wizard-category]').forEach(b=>b.onclick=()=>{category=b.dataset.wizardCategory;show(2);});
    modal.querySelector('#repairBack').onclick=()=>show(Math.max(1,current-1));
    next.onclick=()=>{if(valid(current))show(current+1);};
    form.onsubmit=async event=>{
      event.preventDefault();if(busy)return;
      if(current!==4){if(valid(current))show(current+1);return;}
      if(!readyToSend)return;
      for(const step of [2,3]){show(step);if(!valid(step))return;}show(4);
      error.hidden=true;busy=true;form.querySelectorAll('button').forEach(b=>b.disabled=true);modal.querySelectorAll('[data-wizard-step],[data-close]').forEach(b=>b.disabled=true);
      const keepOpen=event=>event.preventDefault();modal.addEventListener('cancel',keepOpen);
      try{
        const data=new FormData(form);data.set('category',category);const files=data.getAll('attachments').filter(f=>f.size);
        if(files.some(f=>f.size>5*1024*1024))throw Error('Each file must be at most 5 MB.');
        if(files.reduce((n,f)=>n+f.size,0)>25*1024*1024)throw Error('The total photo selection must be 25 MB or less.');
        if(!files.length)data.delete('attachments');
        await api('requests/',{method:'POST',body:data,headers:{'Idempotency-Key':key}});
        modal.close();await onSaved(direct);
      }catch(e){error.textContent=e.message;error.hidden=false;}
      finally{busy=false;modal.removeEventListener('cancel',keepOpen);if(form.isConnected){form.querySelectorAll('button').forEach(b=>b.disabled=false);modal.querySelector('[data-close]').disabled=false;show(current);}}
    };
    show(2);if(!modal.open)modal.showModal();
  }
  return {open};
})();
