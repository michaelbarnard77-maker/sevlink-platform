const repairIconPaths={
 'Plumbing':'<path d="M4 10h16v5h-5v6h-6v-6H4zM12 10V5m-4 0h8M3 10v5m18-5v5"/>',
 'Electrical':'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',
 'Doors & locks':'<path d="M5 22V3h14v19M9 22V7h6v15M12 14h.01M3 22h18"/>',
 'Painting':'<path d="M4 3h14v7H4zM18 6h3v8h-9v3m-2 0h4v5h-4z"/>',
 'Tiling':'<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
 'General maintenance':'<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7"/>',
 'Roofing':'<path d="m2 11 10-8 10 8M4 10v10h16V10M7 7V3h3m-4 9 6-5 6 5"/>',
 'Gutters & Downpipes':'<path d="M3 5h15v5H3zM18 7h3v10a4 4 0 0 1-4 4h-2v-4h2V10M6 2v3m5-3v3"/>',
 'Damp & Waterproofing':'<path d="m12 2 8 3v6c0 5-4 9-8 11-4-2-8-6-8-11V5zM12 7s-3 4-3 6a3 3 0 0 0 6 0c0-2-3-6-3-6Z"/>',
 'Ceilings & Drywall':'<path d="M3 4h18v16H3zM3 9h18M8 9v11M16 9v11M10 4v5"/>',
 'Carpentry & Cupboards':'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M12 3v18M9 10v4m6-4v4M4 17h16"/>',
 'Windows & Glass':'<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M12 3v18M3 12h18m12-5 2-2m-2 5 3-3"/>',
 'Gates & Garage Doors':'<path d="m2 8 10-5 10 5M4 8v13h16V8M7 21V10h10v11M7 14h10M7 18h10"/>',
 'Appliances':'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M5 7h14M8 4.5h.01M11 4.5h.01"/><circle cx="12" cy="14" r="4"/>',
 'Air Conditioning & Ventilation':'<rect x="2" y="3" width="20" height="8" rx="2"/><path d="M5 8h14M7 14v4m5-4v7m5-7v4"/>',
 'Gardens & Outdoor Areas':'<path d="M12 21v-9M12 15C4 15 3 10 3 5c6 0 9 4 9 10Zm0-3c0-6 3-9 9-9 0 6-3 9-9 9ZM6 21h12"/>',
 'Pest Control':'<path d="m8 5-2-3m10 3 2-3M8 9H3m18 0h-5M8 14H2m20 0h-6M8 18l-4 4m12-4 4 4M12 7v13"/><rect x="8" y="5" width="8" height="15" rx="4"/>',
 'Cleaning & Waste Removal':'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
 'Renovations & Refurbishments':'<path d="m2 10 10-8 10 8M5 10v11h7M9 21v-7h4m3-2 5 5-5 5-3-3 5-5M15 13l2-2"/>'
};
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function icon(category){return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${repairIconPaths[category]||repairIconPaths['General maintenance']}</svg>`}
const categories=Object.keys(repairIconPaths);
const featured=[
 {category:'Plumbing',title:'Plumbing repairs',description:'Leaking taps, blocked drains, toilet faults and geyser-related issues. Tell us what you can see and where it’s happening.'},
 {category:'Electrical',title:'Electrical maintenance',description:'Faulty lights, sockets, tripping circuits and power problems. Let us know what is affected so we can discuss the right next step.'},
 {category:'General maintenance',title:'The everyday fixes',description:'Doors, locks, cupboards, ceilings and those small repairs that make a big difference to how a property works.'},
 {category:'Roofing',title:'Roofs & waterproofing',description:'Roof leaks, gutters, damp and water penetration. Help us understand where the problem starts and what needs attention.'},
 {category:'Painting',title:'Painting & tiling',description:'Fresh finishes, damaged paintwork, loose tiles and tired grout. From individual repairs to a wider property refresh.'},
 {category:'Renovations & Refurbishments',title:'Renovations & refurbishments',description:'Kitchens, bathrooms and spaces ready for a new chapter. Talk to us about the changes you have in mind.'}
];
$('#serviceGrid').innerHTML=featured.map((s,i)=>`<article class="service-card"><span class="card-number">0${i+1}</span><div class="service-icon">${icon(s.category)}</div><h3>${s.title}</h3><p>${s.description}</p><button data-service="${esc(s.category)}">Tell us what you need <span>↗</span></button></article>`).join('');
$('#enquiryService').insertAdjacentHTML('beforeend',categories.map(c=>`<option>${esc(c)}</option>`).join('')+'<option>Not sure / something else</option>');
const dialog=$('#siteDialog');let categoryQuery='';
function showDialog(content){$('#dialogContent').innerHTML=content;if(!dialog.open)dialog.showModal()}
function enquire(service=''){if(service&&[...$('#enquiryService').options].some(o=>o.value===service))$('#enquiryService').value=service;if(dialog.open)dialog.close();$('#mainNav').classList.remove('is-open');$('#menuButton').setAttribute('aria-expanded','false');$('#contact').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});$('#enquiryForm').elements.name.focus({preventScroll:true})}
function showCategories(){showDialog(`<p class="eyebrow">HOW CAN WE HELP?</p><h2 class="dialog-title">Find your service.</h2><p class="dialog-description">Search the categories below or tell us about something different.</p><input class="category-search" id="categorySearch" type="search" placeholder="Search plumbing, tiling, renovation…" aria-label="Search service categories" value="${esc(categoryQuery)}"><div id="categoryChoices" class="category-choices"></div>`);const fill=()=>{categoryQuery=$('#categorySearch').value;const matches=categories.filter(c=>c.toLowerCase().includes(categoryQuery.trim().toLowerCase()));$('#categoryChoices').innerHTML=matches.map(c=>`<button class="category-choice" data-category="${esc(c)}">${icon(c)}<span>${esc(c)}</span></button>`).join('')||'<p>No matches. Try another service or choose General maintenance.</p>';$('#categoryChoices').querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>enquire(b.dataset.category))};$('#categorySearch').oninput=fill;fill();$('#categorySearch').focus()}
const serviceExamples={Plumbing:['Leaking taps and pipes','Blocked sinks and drains','Toilet faults','Geyser-related problems'],Electrical:['Lighting and sockets','Tripping circuits','Power faults','Electrical maintenance'],'General maintenance':['Doors and locks','Cupboards and fittings','Walls and ceilings','General property repairs'],Roofing:['Roof leaks and damage','Gutters and downpipes','Waterproofing','Damp and water penetration'],Painting:['Interior and exterior painting','Damaged paint finishes','Tiling and grout repairs','Refreshing a room or property'],'Renovations & Refurbishments':['Kitchen renovations','Bathroom renovations','Property refurbishments','Interior alterations']};
function showService(category){const service=featured.find(s=>s.category===category);if(!service)return;showDialog(`<p class="eyebrow">SEVLINK SERVICES</p><h2 class="dialog-title">${esc(service.title)}</h2><p class="dialog-description">${esc(service.description)}</p><ul class="issue-list">${serviceExamples[category].map(x=>`<li>${esc(x)}</li>`).join('')}</ul><div class="dialog-actions"><button class="button navy" id="enquireAboutService">Enquire about this service <span>↗</span></button></div><p class="preview-note">A few photos and the property location help us discuss the next step.</p>`);$('#enquireAboutService').onclick=()=>enquire(category)}
function enquiryMessage(data){return `SEVLINK PROPERTY ENQUIRY\n\nName: ${data.name}\nPhone: ${data.phone}\nEmail: ${data.email}\nEnquiring as: ${data.clientType}\nProperty area: ${data.area}\nService: ${data.service}\n\nWork requested:\n${data.details}\n\nPlease contact me to discuss the next step.`}
function enquiryLinks(data){const message=enquiryMessage(data),subject='Sevlink enquiry: '+data.service+' · '+data.area;return {message,email:'mailto:maintenance@sevlink.co.za?subject='+encodeURIComponent(subject)+'&body='+encodeURIComponent(message),whatsapp:'https://wa.me/27810285034?text='+encodeURIComponent(message)}}
$('#enquiryForm').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;if(!form.reportValidity())return;const fields=new FormData(form),data={};for(const key of ['name','phone','email','clientType','area','service','details'])data[key]=String(fields.get(key)||'').trim();if(Object.values(data).some(v=>!v)){const error=$('#formError');error.hidden=false;error.textContent='Please complete each field before reviewing your enquiry.';return}$('#formError').hidden=true;const links=enquiryLinks(data);showDialog(`<p class="eyebrow">YOUR ENQUIRY IS READY TO REVIEW</p><h2 class="dialog-title">Let’s get the details right.</h2><p class="dialog-description">Choose how you’d like to send this to Sevlink. No message has been sent yet.</p><div class="enquiry-preview">${esc(links.message)}</div><div class="dialog-actions"><a class="button turquoise" href="${esc(links.whatsapp)}" target="_blank" rel="noopener">Send via WhatsApp <span>↗</span></a><a class="button navy" href="${esc(links.email)}">Open email draft <span>↗</span></a></div><p class="preview-note">WhatsApp or your email app opens with the message prepared. Add any photos there, then send it when you’re ready.</p><button class="back-button" id="editEnquiry">← Back to edit my enquiry</button>`);$('#editEnquiry').onclick=()=>dialog.close()};
$('#enquiryForm').addEventListener('invalid',event=>{const error=$('#formError');error.hidden=false;error.textContent=(event.target.closest('label')?.firstChild?.textContent.trim()||'Required field')+': '+event.target.validationMessage},true);
$('#enquiryForm').addEventListener('input',()=>$('#formError').hidden=true);
document.querySelectorAll('[data-enquire]').forEach(b=>b.onclick=()=>enquire());document.querySelectorAll('[data-service]').forEach(b=>b.onclick=()=>showService(b.dataset.service));$('#allServicesButton').onclick=showCategories;$('#closeDialog').onclick=()=>dialog.close();dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close()}});
$('#menuButton').onclick=()=>{const open=$('#mainNav').classList.toggle('is-open');$('#menuButton').setAttribute('aria-expanded',String(open))};$('#mainNav').querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{$('#mainNav').classList.remove('is-open');$('#menuButton').setAttribute('aria-expanded','false')}));document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('#mainNav').classList.remove('is-open');$('#menuButton').setAttribute('aria-expanded','false')}});
$('#privacyButton').onclick=()=>showDialog(`<p class="eyebrow">YOUR ENQUIRY</p><h2 class="dialog-title">Your details, your choice.</h2><div class="privacy-text"><p>This demo uses the details you enter to prepare a message for you to review. It does not submit the form to a lead database or send a message automatically.</p><p>If you choose WhatsApp or email, the details are passed to that service so you can send your enquiry to Sevlink. Please share only the information needed for the work requested.</p><p>For questions about an enquiry, contact info@sevlink.co.za or call 081 028 5034.</p></div>`);$('#year').textContent=new Date().getFullYear();

// A live sign-in is optional and never points to the browser-local demo implicitly.
if (window.SEVLINK_PORTAL_SIGN_IN_URL) {
  try {
    const livePortal = new URL(window.SEVLINK_PORTAL_SIGN_IN_URL);
    if (livePortal.protocol !== 'https:' || livePortal.username || livePortal.password ||
        livePortal.search || livePortal.hash || !['/', '/login/'].includes(livePortal.pathname)) throw new Error('Invalid portal origin');
    const signIn = document.createElement('a');
    signIn.href = livePortal.origin + '/login/';
    signIn.textContent = 'Agency sign-in';
    document.querySelector('#mainNav').append(signIn);
  } catch (_) { /* Invalid configuration never becomes a visitor-facing link. */ }
}
