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
  // Original Sevlink line illustrations, keyed by category so filtering cannot change their meaning.
  const illustrations={
    "Plumbing": "<path class=\"icon-surface\" d=\"m10 50 47-11 29 15-47 13Z\"/><path d=\"m10 50 29 17 47-13v8L39 76 10 59ZM22 52l33-8 18 9-33 10Z\"/><path d=\"M37 48V23a13 13 0 0 1 26 0v8h-6v-8a7 7 0 0 0-14 0v24m14-16h6v4h-6ZM47 49v-8m-4 2 8-2M24 54v-7m-3 2 6-2M38 76v8m29-16v16\"/><path class=\"icon-accent\" d=\"M60 40v5m0 4v3m-25 5 5 2 5-1\"/><path class=\"icon-detail\" d=\"m15 57 22 13m6 0 36-10M53 16a9 9 0 0 1 7 7\"/>",
    "Electrical": "<rect class=\"icon-surface\" x=\"9\" y=\"23\" width=\"42\" height=\"54\" rx=\"4\"/><rect x=\"14\" y=\"28\" width=\"32\" height=\"44\" rx=\"2\"/><path d=\"M21 45h5v8h-5Zm13 0h5v8h-5ZM28 58h5v8h-5Z\"/><circle cx=\"30\" cy=\"33\" r=\"1\"/><path d=\"M60 35V22h19v13m-23 0h27v13a13 13 0 0 1-13 13h-1a13 13 0 0 1-13-13Zm13 26v8q0 11 15 11M65 22v-8m9 8v-8\"/><path class=\"icon-accent\" d=\"m70 40-7 10h8l-2 7M57 16l-3-3m30 3 3-3M30 13v4\"/><path class=\"icon-detail\" d=\"M17 68h4m37-28h23\"/>",
    "Doors & locks": "<path class=\"icon-surface\" d=\"M13 83V12h49v71ZM20 19h35v58H20Z\"/><path d=\"m20 19 30 6v59l-30-7Zm30 6 5-6M26 31l18 3v18l-18-2Zm0 26 18 2v16l-18-3ZM13 83h43M8 87h55\"/><path d=\"M43 52h9m-9 0v5M67 58V47a9 9 0 0 1 18 0v11\"/><rect class=\"icon-surface\" x=\"62\" y=\"58\" width=\"28\" height=\"25\" rx=\"3\"/><path class=\"icon-accent\" d=\"M70 58V47a6 6 0 0 1 12 0v11\"/><circle cx=\"76\" cy=\"68\" r=\"3\"/><path d=\"M76 71v5\"/>",
    "Painting": "<rect class=\"icon-surface\" x=\"10\" y=\"12\" width=\"51\" height=\"23\" rx=\"5\"/><path d=\"M61 18h14v27H43v12M10 17H7v13h3M15 16v15m41-15v15\"/><rect class=\"icon-surface\" x=\"38\" y=\"57\" width=\"10\" height=\"27\" rx=\"4\"/><path d=\"M42 62v16m6-18 9-10M58 62l28-4 6 22-28 6Z\"/><path class=\"icon-detail\" d=\"m62 64 21-3 4 15-21 4Zm1 3 19-3m-18 7 19-3m-18 7 19-3\"/><path class=\"icon-accent\" d=\"M21 18h29M21 23h21m-21 5h14M71 79l10-2\"/>",
    "Tiling": "<path class=\"icon-surface\" d=\"m9 40 48-18 31 20-47 32Z\"/><path d=\"m9 40 32 34v8L9 48Zm32 34 47-32v8L41 82ZM22 35l34 29M37 29l35 24M53 24l33 21M18 49l48-21M29 61l49-24\"/><path d=\"m12 15 13-6 16 9-12 8Z\"/><path class=\"icon-detail\" d=\"m12 15 17 11v4L12 19Zm17 11 12-8v4l-12 8M14 44l25 26m6 5 37-25\"/><path class=\"icon-accent\" d=\"m37 44 7-3m-3 8 7-3m10 14 7-4\"/>",
    "General maintenance": "<path class=\"icon-surface\" d=\"M10 42h75v40H10Z\"/><path d=\"M10 51h75M10 63h75M35 42v-8h25v8M40 34v-5h15v5M19 57h8v12h-8Zm48 0h8v12h-8ZM15 82v4h65v-4\"/><path d=\"m20 41-8-21 8-4 11 25m-17-21 6-3M43 41V17l-4-6 5-5 5 5-2 6v24M61 41l10-24-4-7 4-6 2 8 5 2 5-5 1 8-8 4-8 20\"/><path class=\"icon-accent\" d=\"M36 69h24v6H36Z\"/><path class=\"icon-detail\" d=\"M14 46h67M31 77h33m-45-48 5-2\"/>",
    "Roofing": "<path class=\"icon-surface\" d=\"m8 48 24-28 33-10 24 28-33 10Z\"/><path d=\"m8 48 24-28 24 28H8Zm0 0v33h48V48l33-10v33L56 81M20 81V58h17v23M8 85h48\"/><path class=\"icon-accent\" d=\"m40 29 33-10m-25 20 33-10M43 17l24 28m-13-31 24 28M17 38h30m-24-8h16M24 65v11\"/><path class=\"icon-surface\" d=\"M64 22V8l9 3v14Zm0-14 7-3 9 3v14l-7 3M73 11l7-3\"/><path class=\"icon-detail\" d=\"m62 61 20-6m-20 12 20-6m-20 12 20-6\"/>",
    "Gutters & Downpipes": "<path class=\"icon-surface\" d=\"m9 25 36-13 38 14-36 13Z\"/><path d=\"m9 25 38 14 36-13v7L47 47 9 33ZM47 39v8M14 35v38l26 10M53 45v9l8 6v22h9V54l-8-6v-7m-1 41h13M61 65h9m-9 10h9M57 51l7-3\"/><path class=\"icon-detail\" d=\"m18 24 29 10 26-9M18 47l20 7m-20 5 20 7m-20 5 20 7M25 39v8m4 4v8\"/><path class=\"icon-accent\" d=\"M80 43s-6 9-6 12a6 6 0 0 0 12 0c0-3-6-12-6-12ZM24 14v4m8-7v4M38 62v8m0 5v3\"/>",
    "Damp & Waterproofing": "<path class=\"icon-surface\" d=\"M12 13h48v64L12 86Z\"/><path d=\"m60 13 25 12v59l-25-7M12 72l48-9 25 11M12 36h48M12 55h48m-32-42v23m15 0v19m-15 0v14\"/><path class=\"icon-detail\" d=\"m18 60 4-3 4 2 5-4 5 4 6-3 5 3v9l-29 5ZM66 31l12 6m-12 7 12 6m-12 7 12 6\"/><path class=\"icon-accent\" d=\"M69 59s-12 14-12 21a12 12 0 0 0 24 0c0-7-12-21-12-21Z\"/><path d=\"m64 80 4 4 7-9\"/><path class=\"icon-accent\" d=\"M22 43v5m7-8v8m7-4v4\"/>",
    "Ceilings & Drywall": "<path class=\"icon-surface\" d=\"M10 16h76v65H10Z\"/><path d=\"m10 16 17 16h42l17-16M27 32v37l-17 12m59-49v37l17 12M27 69h42M10 53h17m42 0h17\"/><path class=\"icon-detail\" d=\"M30 16v16m18-16v16m18-16v16M17 22h61M34 42h27v21H34ZM34 49h27m-27 7h27m-18-14v21\"/><path class=\"icon-accent\" d=\"m47 34-5 5 6 4-4 6 6 5-3 6m17-17 4 2M19 58v10m58-10v10\"/>",
    "Carpentry & Cupboards": "<path class=\"icon-surface\" d=\"M14 16h57v62H14Z\"/><path d=\"m71 16 13 8v60l-13-6M14 16l13-7 57 15M14 35h57M42 16v62M19 21h18v9H19Zm28 0h18v9H47ZM19 40h18v31H19Zm28 0h18v31H47ZM14 78v7h6v-7m45 0v7h6v-7\"/><path class=\"icon-accent\" d=\"M34 49v11m16-11v11M24 26h8m20 0h8\"/><path class=\"icon-detail\" d=\"m75 29 5 3v45l-5-3M24 44v23m3-23v23M15 12l55 1\"/>",
    "Windows & Glass": "<path class=\"icon-surface\" d=\"M12 12h69v70H12Z\"/><path d=\"M18 18h57v57H18ZM46 18v57M18 46h28m0 0h29M8 82h78v5H8ZM18 18l22 8v55l-22-6Zm6 9 10 4v17l-10-3Zm0 24 10 3v17l-10-3ZM40 48h4\"/><path class=\"icon-accent\" d=\"m54 34 11-10m-12 17 17-16m-13 42 9-8\"/><path class=\"icon-detail\" d=\"M50 22h21v20H50Zm0 28h21v21H50Z\"/>",
    "Gates & Garage Doors": "<path class=\"icon-surface\" d=\"m8 33 39-22 40 22v49H8Z\"/><path d=\"m6 33 41-25 43 25M15 32h65v50H15ZM21 39h53v43H21ZM21 48h53m-53 9h53m-53 9h53m-53 9h53M7 82h83\"/><path class=\"icon-detail\" d=\"M42 61h10m-26-18h44M35 17V9h22v8M39 9V5h14v4M83 42h6v10h-6\"/><path class=\"icon-accent\" d=\"M37 75h20M28 33h39m-36-5 16-9 17 9\"/>",
    "Appliances": "<rect class=\"icon-surface\" x=\"8\" y=\"30\" width=\"44\" height=\"53\" rx=\"3\"/><path d=\"M8 43h44m-40-7h3m5 0h3m12 0h10M13 83v4m33-4v4M62 12h24v72H62ZM62 38h24M67 24v8m0 14v15\"/><circle cx=\"30\" cy=\"63\" r=\"15\"/><circle class=\"icon-detail\" cx=\"30\" cy=\"63\" r=\"11\"/><path class=\"icon-accent\" d=\"M20 63c7-8 13 8 21 0M63 17h18\"/><path class=\"icon-detail\" d=\"M67 68h14v11H67ZM55 84h35\"/>",
    "Air Conditioning & Ventilation": "<rect class=\"icon-surface\" x=\"8\" y=\"15\" width=\"80\" height=\"33\" rx=\"5\"/><path d=\"M12 38h72M16 24h61m-61 6h61M18 42h59m-59 4h59M76 20h4\"/><path class=\"icon-detail\" d=\"M21 39v8m9-8v8m9-8v8m9-8v8m9-8v8m9-8v8m9-8v8\"/><path class=\"icon-accent\" d=\"M27 56v14q0 9-10 9m31-23v28m21-28v14q0 9 10 9M19 60h6m20 7h6m20-7h6\"/><path class=\"icon-detail\" d=\"M13 19h57\"/>",
    "Gardens & Outdoor Areas": "<path class=\"icon-surface\" d=\"M28 15a11 11 0 0 0-20 7A13 13 0 0 0 12 46a13 13 0 0 0 24-6 13 13 0 0 0-8-25Z\"/><path d=\"M24 33v46m0-28-9-9m9 17 11-10M44 37l6-5 6 5v33H44Zm16 0 6-5 6 5v33H60Zm16 0 6-5 6 5v33H76ZM39 45h49M39 59h49M9 80h79\"/><path class=\"icon-accent\" d=\"M12 80v-8m0 4-4-4m4 2 5-4m20 10v-8m0 4 4-4M43 88l11-8m7 8 9-8m-20 4h35\"/><path class=\"icon-detail\" d=\"M15 27q6-8 11-3m-12 8 5-1\"/>",
    "Pest Control": "<path class=\"icon-surface\" d=\"M14 62c-1-15 15-22 31-18 9 2 16 10 16 19l-10 8H27Z\"/><path d=\"M61 63l12 6-12 6H32m-5-4-6 8h13m16-10-5 10h11M17 65C2 66 1 79 12 83q7 2 12-3\"/><circle cx=\"49\" cy=\"47\" r=\"8\"/><circle class=\"icon-detail\" cx=\"49\" cy=\"47\" r=\"4\"/><circle cx=\"61\" cy=\"61\" r=\"1\"/><path class=\"icon-accent\" d=\"m72 66 13-3m-12 7h14m-15 4 13 3\"/><path d=\"M14 15h27v20H14Zm4 0v-5h19v5\"/><path class=\"icon-detail\" d=\"m20 21 15 8m0-8-15 8M62 18h19v20H62Z\"/><path class=\"icon-accent\" d=\"M67 24h9m-9 7h9\"/>",
    "Cleaning & Waste Removal": "<path class=\"icon-surface\" d=\"m12 58 20-8 13 28-24 9ZM52 44h32l-4 40H56Z\"/><path d=\"m23 53 22-42 5 3-22 41M12 58l20 20 13-1M52 44q16-9 32 0M58 47v-9q10-11 20 0v9M59 54h18v22H59Z\"/><path class=\"icon-detail\" d=\"m17 62 14 18m-9-20 13 17m-9-19 13 16M64 58v13m8-13v13\"/><path class=\"icon-accent\" d=\"M48 26h7m-3-4v8M12 42h8m-4-4v8M65 18h8m-4-4v8\"/>",
    "Renovations & Refurbishments": "<path class=\"icon-surface\" d=\"M9 17h77v66H9Z\"/><path d=\"m9 17 16 15h45l16-15M25 32v39L9 83m61-51v39l16 12M25 71h45M12 53h13m45 0h16M34 47h20v24H34Z\"/><path d=\"m57 82 13-48 13 48M62 63h16m-18 9h20m-16-17h12m-10-8h8\"/><path class=\"icon-accent\" d=\"M30 24h27v10H30Zm27 4h5v14H45v8m-3 0h6v14h-6Z\"/><path class=\"icon-detail\" d=\"M13 22h12m49 0h8M34 76h14m-21 4h18\"/>"
};
  const categoryExamples={"Plumbing": "Taps, toilets and leaks", "Electrical": "Power, sockets and lighting", "Doors & locks": "Handles, hinges and locks", "Painting": "Walls, paint and finishes", "Tiling": "Tiles, grout and flooring", "General maintenance": "Small repairs and odd jobs", "Roofing": "Roof tiles, sheets and leaks", "Gutters & Downpipes": "Blocked gutters and drainage", "Damp & Waterproofing": "Damp walls and water damage", "Ceilings & Drywall": "Cracks, holes and ceiling damage", "Carpentry & Cupboards": "Cabinets, shelves and woodwork", "Windows & Glass": "Frames, panes and broken glass", "Gates & Garage Doors": "Gates, motors and garage doors", "Appliances": "Ovens, hobs and appliances", "Air Conditioning & Ventilation": "Cooling, airflow and extractor fans", "Gardens & Outdoor Areas": "Gardens, fences and outdoor repairs", "Pest Control": "Insects, rodents and infestations", "Cleaning & Waste Removal": "Cleaning, rubbish and waste", "Renovations & Refurbishments": "Room upgrades and larger projects"};
  const categoryDescription=name=>categoryExamples[name]||'Repairs and maintenance';
  const categoryIcon=name=>`<svg class="repair-illustration" viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${illustrations[name]||illustrations['General maintenance']}</svg>`;
  const navigationPaths={
    overview:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
    requests:'M8 5H5v16h14V5h-3M9 3h6v4H9zm0 9h6m-6 4h6',
    properties:'m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7',
    tenants:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3m18 0v-3a4 4 0 0 0-3-4M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8m8 0a4 4 0 0 1 0 8',
    profile:'M3 21h18M5 21V7l7-4 7 4v14M9 9h1m4 0h1m-6 4h1m4 0h1m-6 8v-4h6v4',
    report:'M14 4 7 11l-2 8 8-2 7-7zM13 5l6 6M3 3v6m-3-3h6',
    calendar:'M4 5h16v16H4zM8 3v4m8-4v4M4 10h16m-12 4h2m4 0h2m-8 4h2',
    updates:'M5 17h14l-2-4V9A5 5 0 0 0 7 9v4zm5 3a2 2 0 0 0 4 0M12 2v2',
    quotes:'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7m-7 4h4',
    accounts:'M3 7h18v14H3zM3 11h18M6 7V3h12v4m-3 12h3m-3-4h3M7 14v4',
    issues:'M4 21V3h14l-3 4 3 4H4m4 4h12v6H8z',
    agencies:'M3 21V9h8v12m0-17h10v17M6 12h2m-2 4h2m6-9h4m-4 4h4m-4 4h4M1 21h22',
    regions:'M14 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0M2 21v-4a5 5 0 0 1 10 0v4m3-7 3-3 4 4-3 3-4-4m-3 7 4-4'
  };
  const navIcon=key=>{key=({publicCalendar:'calendar',monday:'accounts',websiteIssues:'issues'})[key]||key;return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${navigationPaths[key]||navigationPaths.requests}"/></svg>`;};
  const field=(name,label,type='text',value='')=>`<label>${esc(label)}</label><input name="${name}" type="${type}" value="${esc(value)}" required>`;
  const select=(name,label,options)=>`<label>${esc(label)}</label><select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('')}</select>`;
  function installBookingTimePicker(input,label){
    input.readOnly=true;input.classList.add('booking-time-input');input.setAttribute('aria-haspopup','dialog');input.setAttribute('aria-expanded','false');
    const popup=document.createElement('section');popup.className='booking-time-picker';popup.hidden=true;popup.setAttribute('role','dialog');popup.setAttribute('aria-label',label);
    popup.innerHTML=`<div class="booking-time-heading"><strong>${esc(label)}</strong><button type="button" class="secondary" aria-label="Close time selector">×</button></div><p>South African time · select a time</p><div class="booking-time-options">${Array.from({length:96},(_,i)=>{const value=String(Math.floor(i/4)).padStart(2,'0')+':'+String(i%4*15).padStart(2,'0');return `<button type="button" data-time="${value}" aria-pressed="false">${value}</button>`;}).join('')}</div>`;
    input.after(popup);const close=()=>{popup.hidden=true;input.setAttribute('aria-expanded','false');};
    const open=()=>{input.form.querySelectorAll('.booking-time-picker').forEach(p=>p.hidden=true);input.form.querySelectorAll('.booking-time-input').forEach(p=>p.setAttribute('aria-expanded','false'));popup.hidden=false;input.setAttribute('aria-expanded','true');let selected;
      popup.querySelectorAll('[data-time]').forEach(b=>{const active=b.dataset.time===input.value;b.setAttribute('aria-pressed',String(active));if(active)selected=b;});
      if(selected){const list=popup.querySelector('.booking-time-options');list.scrollTop=selected.offsetTop-list.offsetTop-list.clientHeight/2;selected.focus({preventScroll:true});}
    };
    input.onclick=()=>popup.hidden?open():close();input.onkeydown=e=>{if(['Enter',' ','ArrowDown'].includes(e.key)){e.preventDefault();open();}};
    popup.onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.time){input.value=b.dataset.time;input.dispatchEvent(new Event('change',{bubbles:true}));}close();input.focus({preventScroll:true});};
    popup.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();input.focus({preventScroll:true});}};
    input.form.addEventListener('click',e=>{if(e.target!==input&&!popup.contains(e.target))close();});
  }
  function decorate(){
    document.querySelectorAll('.categorygrid .category').forEach(b=>{b.querySelector('span').innerHTML=categoryIcon(b.dataset.category);});
    document.querySelectorAll('#nav .nav-icon,#phoneNav button>span').forEach(n=>{n.innerHTML=navIcon(n.closest('[data-view]').dataset.view);});
  }
  const selectedStages=new Map();
  async function stages({api,app,showDetail,toast,context}){
    try{
      const d=await api('workflow/stages/');if(!app.isConnected || document.querySelector('[data-view=overview].active')===null)return;
      app.querySelector('#workflowStages')?.remove();app.querySelector('.stats')?.remove();app.querySelector('.heading')?.remove();
      if(['pm','admin'].includes(context?.user.role))app.querySelector('#rows')?.closest('.panel')?.remove();
      (app.querySelector('#attention') || app).insertAdjacentHTML(app.querySelector('#attention')?'afterend':'afterbegin',`<section class="workflow-overview${context?.user.role==='superadmin'?' ops-overview':''}" id="workflowStages">${context?.user.role==='superadmin'?'<div class="heading"><div><span class="eyebrow">SEVLINK OPERATIONS</span><h1>Your maintenance control room.</h1><p>Every request has a place. Every job has a clear next action.</p></div></div>':'<span class="eyebrow">MAINTENANCE OVERVIEW</span><h2>Maintenance Overview</h2>'}${d.summary?`<div class="stats">${d.summary.map(s=>`<div class="stat"><label>${esc(s.label)}</label><strong>${s.count}</strong><small>Saved maintenance records</small></div>`).join('')}</div>`:''}<div class="${d.stages.length===8?'stage-grid pm-stage-grid':'ops-pods'}">${d.stages.map((s,i)=>d.stages.length===8?`<button class="stage-card" data-stage="${s.key}"><span class="stage-icon">${icon(i)}</span><strong>${s.count}</strong><b>${esc(s.label)}</b><small>View jobs →</small></button>`:`<button class="ops-pod stage-card" data-stage="${s.key}"><span>${esc(s.label)}</span><b>${s.count}</b><small>View jobs →</small></button>`).join('')}</div><div id="stageJobs"></div>${d.upcoming.length?`<section class="panel"><h2>Upcoming attendance</h2>${d.upcoming.map(a=>`<article class="workflow-job-row" data-upcoming="${a.id}" role="button" tabindex="0" aria-label="Open job"><div><strong>${esc(a.property)}</strong><p>${esc(a.reference)} · ${esc(a.date)} · ${esc(a.window)}</p></div></article>`).join('')}</section>`:''}</section>`);
      if(context?.user.role==='superadmin'&&d.rescheduling?.length){
        app.querySelector('#workflowStages').insertAdjacentHTML('afterbegin',`<section class="panel rescheduling-attention"><span class="eyebrow">SEVLINK ACTION REQUIRED</span><h2>Needs rescheduling (${d.rescheduling.length})</h2>${d.rescheduling.map(a=>`<article class="workflow-job-row"><div><strong>${esc(a.reference)} · ${esc(a.property)}</strong><p>Cancelled appointment: ${esc(a.date)}</p><p>${esc(a.reason)}</p></div><button class="primary" data-reschedule-cancelled="${a.appointment}" data-reschedule-job="${a.job}">Reschedule appointment</button></article>`).join('')}</section>`);
        app.querySelectorAll('[data-reschedule-cancelled]').forEach(b=>b.onclick=async()=>{try{const saved=await api(`requests/${b.dataset.rescheduleJob}/`);showDetail(saved);const modal=document.querySelector('#modal');modal.querySelector('[data-tab=attendance]').click();const arrival=saved.workflow.attendance.find(a=>String(a.appointment_id)===b.dataset.rescheduleCancelled);if(arrival)modal.querySelector(`[data-confirm-arrival="${arrival.id}"][data-arrival-action="replace-cancelled"]`)?.click();}catch(e){toast(e.message);}});
      }
      app.querySelectorAll('[data-upcoming]').forEach(b=>b.onclick=async()=>{try{showDetail(await api(`requests/${b.dataset.upcoming}/`));}catch(e){toast(e.message);}});
      let stageRequest=0;
      app.querySelectorAll('[data-stage]').forEach(b=>b.onclick=async event=>{
        const request=++stageRequest;
        try{const r=await api('workflow/stages/?stage='+b.dataset.stage);if(request!==stageRequest||!b.isConnected)return;selectedStages.set(context?.user.role,b.dataset.stage);app.querySelectorAll('[data-stage]').forEach(c=>{c.classList.toggle('selected',c===b);c.setAttribute('aria-pressed',String(c===b));});const panel=app.querySelector('#stageJobs');if(!panel)return;
          panel.innerHTML=`<section class="panel"><h2>${esc(d.stages.find(s=>s.key===b.dataset.stage).label)}</h2><div class="cards">${r.results.map(j=>`<article class="card job-card" data-stage-job="${j.id}" role="button" tabindex="0" aria-label="Open job"><div class="toolbar"><span class="eyebrow">${esc(j.reference)}</span><span class="badge">${esc(({normal:'Normal',high:'High',urgent:'Urgent',safety:'Safety'})[j.urgency]||j.status)}</span>${j.safety_concern?'<span class="badge Urgent">Safety concern flagged</span>':''}</div><h2>${esc(j.property)}</h2><p><b>${esc(j.title)}</b><br>${esc(j.property_name||'')}<br>${esc(j.agency||'')}</p>${b.dataset.stage==='attention'&&j.attention_actions?.length?`<div class="notice job-attention-reasons"><h3>Action required</h3><ul>${j.attention_actions.map(a=>`<li><strong>${esc(a.action)}</strong>${Number(a.amount)>0?` · R ${esc(Number(a.amount).toLocaleString('en-ZA',{minimumFractionDigits:2,maximumFractionDigits:2}))}`:''}${a.due_date?` · Due ${esc(a.due_date)}`:''}${a.appointment_date?` · Appointment ${esc(new Date(a.appointment_date).toLocaleString('en-ZA',{timeZone:'Africa/Johannesburg'}))}`:''}</li>`).join('')}</ul></div>`:''}</article>`).join('')||'<p>No jobs in this stage.</p>'}</div></section>`;
          panel.querySelectorAll('[data-stage-job]').forEach(c=>c.onclick=async()=>{try{showDetail(await api(`requests/${c.dataset.stageJob}/`));}catch(e){toast(e.message);}});
          if(event?.isTrusted)panel.scrollIntoView({block:'nearest',behavior:'smooth'});
        }catch(e){toast(e.message);}
      });
      if(context?.user.role==='superadmin')app.querySelectorAll(':scope > .panel').forEach(p=>p.remove());
      const selectedStage=selectedStages.get(context?.user.role)||(context?.user.role==='superadmin'?'new':null);
      if(selectedStage)app.querySelector(`[data-stage="${selectedStage}"]`)?.click();
    }catch(e){toast(e.message);}
  }
  let inboxGeneration=0;
  async function inbox({api,app,showDetail,toast}){
    const generation=++inboxGeneration;
    try{const d=await api('workflow/notifications/');if(generation!==inboxGeneration || !document.querySelector('[data-view=updates].active'))return;document.dispatchEvent(new CustomEvent('sevlink-notifications-changed',{detail:{unread:d.unread}}));app.innerHTML=`<div class="heading"><div><span class="eyebrow">SAVED JOB UPDATES</span><h1>Updates & Notifications</h1><p>${d.unread} unread</p></div></div>${d.results.map(n=>`<article class="panel"><h2>${esc(n.label)}</h2><p>${esc(n.reference)} · ${esc(n.property)} · ${esc(new Date(n.at).toLocaleString('en-ZA'))}</p><button class="primary" data-notice="${n.id}" data-notice-job="${n.job}">Open job</button> <button class="secondary" data-notice-read="${n.id}" data-read="${!n.read}">${n.read?'Mark unread':'Mark read'}</button></article>`).join('')||'<section class="panel">No saved notifications yet.</section>'}`;
      app.querySelectorAll('[data-notice]').forEach(b=>b.onclick=async()=>{await api(`workflow/notifications/${b.dataset.notice}/`,{method:'POST',body:JSON.stringify({read:true})});document.dispatchEvent(new CustomEvent('sevlink-notifications-changed'));showDetail(await api(`requests/${b.dataset.noticeJob}/`));});
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
    const nextSteps={new:staff?(w.operations_triage==='attendance'?'Attendance is needed before quoting. Confirm the authorised attendance arrangements.':'Choose Attendance needed or Prepare desktop quote.'):pm?'Review and route this maintenance request.':'The property manager is reviewing this request.',quoting:'Sevlink is preparing the quotation.',declined:'The PM declined the quotation. Review the decision in Quotes.',approval:staff?'Waiting PM approval':tenant?'Your property manager is reviewing the proposed work.':'Review the quotation and record your decision.',deposit:tenant?'Sevlink is preparing attendance arrangements.':'Awaiting the required confirmed payment and Sevlink verification.',ready:'Please confirm attendance date.',booked:'Review the confirmed attendance window and access arrangements.',underway:'Follow the work and share permitted progress updates.',invoice:'Completion documentation and the final invoice are being prepared.',payment:tenant?'The completed work is being finalised.':'Review the final invoice and outstanding payment.',closed:'This job remains available in the authorised history.'};
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
        document.dispatchEvent(new CustomEvent('sevlink-notifications-changed'));
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
    if(staff&&w.can_triage){
      panels.overview.insertAdjacentHTML('afterbegin',`<section class="panel"><h2>Assess new request</h2><p>Choose how Sevlink will assess this repair.</p>${w.operations_triage?`<p><strong>${w.operations_triage==='attendance'?'Attendance needed':'Desktop quote selected'}</strong></p>`:''}<div class="actions">${[['attendance','Attendance needed'],['desktop','Prepare desktop quote']].map(([value,label])=>`<form class="operations-triage"><input type="hidden" name="decision" value="${value}"><button type="submit" class="primary">${label}</button></form>`).join('')}</div>${w.operations_triage==='attendance'?'<p>A free assessment visit can be booked in Attendance. This does not authorise repair work.</p>':''}</section>`);
      panels.overview.querySelectorAll('.operations-triage').forEach(f=>submit(f,'operations-triage'));
      if(!w.operations_triage||w.operations_triage==='attendance')panels.quotes.querySelector('#quoteForm')?.remove();
    }
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
    const currentAttendance=w.attendance.find(a=>a.status==='confirmed'&&(a.purpose!=='assessment'||w.free_assessment));
    const needsReschedule=Boolean(currentAttendance);
    panels.attendance.innerHTML=['completed','closed','cancelled'].includes(job.status)?'<div class="notice"><h2>Attendance history</h2><p>This job is '+(job.status==='cancelled'?'cancelled':'complete')+'. Previous attendance arrangements remain available below.</p></div>':w.attendance_ready?'<div class="notice"><h2>Please confirm attendance date</h2><p>This job is ready for attendance arrangements.</p></div>':'<div class="notice"><h2>Attendance arrangements are locked</h2><p>Complete the required work authorisation before arranging attendance.</p></div>';
    if(w.free_assessment)panels.attendance.innerHTML='<div class="notice"><h2>Free quotation assessment</h2><p>Arrange an assessment visit to prepare the quote. No deposit is required. Repair work still requires quotation approval and deposit verification.</p></div>';
    if(staff && w.attendance_ready && !['completed','closed','cancelled'].includes(job.status) && !w.attendance.some(a=>['pending','confirmed'].includes(a.status))){
      panels.attendance.innerHTML=`<div class="notice"><h2>${w.free_assessment?'Free quotation assessment':'Awaiting preferred attendance date'}</h2><p>The designated access contact has been asked for a preferred date and arrival window. Return here to confirm the appointment once their request arrives.</p></div>`;
    }
    if(staff&&w.free_assessment&&!w.attendance.some(a=>['pending','confirmed'].includes(a.status))){
      panels.attendance.insertAdjacentHTML('beforeend','<form id="arrangeAssessment"><input type="hidden" name="preference" value="call"><button class="primary" type="submit">Arrange assessment directly</button></form>');submit(panels.attendance.querySelector('#arrangeAssessment'),'attendance-request');
    }
    if(!tenant && !w.attendance_ready && w.deposit?.blockers?.length){
      panels.attendance.innerHTML=`<div class="notice"><h2>Attendance arrangements are locked</h2><p>${esc(w.deposit.blockers.join(' '))}</p><button class="secondary" type="button" id="attendanceDeposit">Review deposit</button></div>`;
      panels.attendance.querySelector('#attendanceDeposit').onclick=()=>show('invoices');
    }
    if(needsReschedule&&w.attendance_ready&&!['completed','closed','cancelled'].includes(job.status))panels.attendance.innerHTML='<div class="notice"><h2>Need to reschedule</h2><p>The appointment is confirmed. Request a new date only if it needs to change.</p></div>';
    if(w.can_arrange_attendance && !w.needs_rescheduling && w.attendance_ready && !w.attendance.some(a=>a.status==='pending')){
      panels.attendance.insertAdjacentHTML('beforeend',`<form id="attendanceRequest" class="panel">${select('preference',needsReschedule?'Reschedule options':'Attendance options',[['date','Select Preferred Date'],['call','Request a Call']])}${field('date',needsReschedule?'New preferred date':'Preferred date','date')}${select('window','Subcontractor arrival window',w.arrival_windows.map(v=>[v,v]))}<p>These are arrival windows, not the length of the job. A preferred date is not a confirmed booking.</p>${needsReschedule?'<p>Your current appointment stays confirmed until Sevlink confirms the new date.</p>':''}<button type="submit" class="primary">${needsReschedule?'Send reschedule request':'Send attendance request'}</button></form>`);
      const f=panels.attendance.querySelector('form');f.elements.preference.onchange=()=>{f.elements.date.required=f.elements.preference.value==='date';f.elements.date.disabled=f.elements.preference.value==='call';f.elements.window.disabled=f.elements.preference.value==='call';};submit(f,'attendance-request');
    }
    const attendanceDate=value=>value?new Date(value+'T12:00:00+02:00').toLocaleDateString('en-ZA',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Africa/Johannesburg'}):'Date to be arranged';
    for(const a of w.attendance){
      const confirmed=a.status==='confirmed',day=confirmed?a.agreed_date:a.requested_date,window=confirmed?a.agreed_window:a.requested_window;
      const status=a.appointment_status==='on_site'?'On site':a.appointment_status==='completed'?'Complete':{pending:'Awaiting confirmation',confirmed:'Confirmed appointment',declined:'Alternative date needed',cancelled:'Cancelled appointment'}[a.status]||a.status;
      panels.attendance.insertAdjacentHTML('beforeend',`<section class="panel attendance-card" data-appointment-status="${esc(a.appointment_status||'booked')}"><div class="attendance-card-header"><span class="eyebrow">${a.purpose==='assessment'?'FREE QUOTATION ASSESSMENT':confirmed?'CONFIRMED ATTENDANCE':'REQUESTED ATTENDANCE'}</span><span class="badge ${a.appointment_status==='completed'?'Completed':a.appointment_status==='on_site'?'OnSite':a.status==='cancelled'?'Cancelled':'Awaiting'}">${esc(status)}</span></div><h2 class="attendance-date">${esc(a.preference==='call'&&!day?'Call requested':attendanceDate(day))}</h2>${window?`<p class="attendance-window"><span>Arrival window</span><strong>${esc(window)}</strong><small>South African time · arrival window, not job duration</small></p>`:'<p class="attendance-window">The PM has requested a call to arrange a suitable date.</p>'}${confirmed&&a.requested_date&&a.requested_date!==a.agreed_date?`<p>Originally requested: ${esc(attendanceDate(a.requested_date))}</p>`:''}${staff&&w.attendance_ready&&(a.purpose!=='assessment'||w.free_assessment)&&!(a.status==='cancelled'&&a.replacement_exists)?`<div class="actions attendance-actions">${confirmed?`<button class="secondary" type="button" data-arrival-action="alternative" data-confirm-arrival="${a.id}">Reschedule</button><button class="primary" type="button" data-arrival-action="additional" data-confirm-arrival="${a.id}">Add appointment</button>`:a.status==='cancelled'&&!a.replacement_exists?`<button class="primary" type="button" data-arrival-action="replace-cancelled" data-confirm-arrival="${a.id}">Reschedule cancelled appointment</button>`:`<button class="primary" type="button" data-arrival-action="accept" data-confirm-arrival="${a.id}">Accept</button><button class="secondary" type="button" data-arrival-action="alternative" data-confirm-arrival="${a.id}">Decline</button>`}</div><div data-arrival-form="${a.id}"></div>`:''}</section>`);
      panels.attendance.querySelectorAll(`[data-confirm-arrival="${a.id}"]`).forEach(b=>b.onclick=async()=>{
        const container=panels.attendance.querySelector(`[data-arrival-form="${a.id}"]`),generation=crypto.randomUUID();container.dataset.generation=generation;container.innerHTML='<p role="status">Loading appointment options…</p>';
        try{const calendar=await api('operations/calendar/');if(container.dataset.generation!==generation)return;const alternative=b.dataset.arrivalAction==='alternative',adding=['additional','replace-cancelled'].includes(b.dataset.arrivalAction),replacing=b.dataset.arrivalAction==='replace-cancelled';
          const previousBookings=!adding&&!confirmed?w.attendance.filter(other=>other.status==='confirmed'&&other.purpose===a.purpose&&other.appointment_id):[];
          const previousBooking=!adding&&!confirmed&&w.attendance.find(other=>other.status==='confirmed'&&other.purpose===a.purpose&&other.appointment_id);
          const needsContact=adding||alternative||a.preference==='call'||a.status!=='pending'||Boolean(previousBooking);
          container.innerHTML=`<form class="attendance-decision"><h3>${adding?'Add appointment':alternative?'Choose an alternative date':'Confirm attendance booking'}</h3><p>${alternative?'Enter the new date agreed with the client and subcontractor by phone, then select the subcontractor.':'The preferred date is retained. Record the date and time agreed with the subcontractor by phone for this property.'}</p>${field('date',adding?'New appointment date':alternative?'Alternative attendance date':'Attendance date','date',adding||alternative?'':a.agreed_date||a.requested_date||'')}${previousBookings.length>1?select('replace_visit','Appointment to reschedule',[['','Select the existing appointment'],...previousBookings.map(row=>[String(row.id),`${row.agreed_date} · ${row.agreed_window}`])]):''}${select('window','Arrival window',w.arrival_windows.map(v=>[v,v]))}<div class="booking-contact">${'<label><input type="checkbox" name="client_confirmed"> I have agreed this date with the client / tenant</label>'+select('contact_category','Who was contacted?',[['','Select contact'],['tenant','Tenant'],['pm','Property Manager'],['other','Other Authorised Contact']])}</div>${select('subcontractor','Assign subcontractor',[['','Select subcontractor'],...calendar.suppliers.map(s=>[s.id,s.name])])}${select('duration','Booking duration',[['day','1 day · 09:00–17:00'],...Array.from({length:7},(_,i)=>[String(i+1),`${i+1} hour${i?'s':''}`])])}${field('start','Booking start time','text','09:00')}${field('end','Booking end time','text','10:00')}${!adding&&(alternative||confirmed||previousBooking)?'<label>Reason for alternative date</label><textarea name="reason" required maxlength="1000"></textarea>':''}<div class="actions"><button type="submit" class="primary">${alternative?'Confirm alternative appointment':'Confirm booking'}</button></div><p role="alert" hidden></p></form>`;
          const f=container.querySelector('form'),key=crypto.randomUUID();
          if(!adding&&!alternative&&a.preference==='date'&&a.status==='pending'){f.elements.date.readOnly=true;f.elements.window.disabled=true;}
          f.elements.window.value=a.agreed_window||a.requested_window||w.arrival_windows[0];
          if(f.elements.replace_visit)f.elements.replace_visit.required=true;
          f.elements.duration.value='1';f.elements.end.readOnly=true;
          const durationChanged=()=>{
            const full=f.elements.duration.value==='day';f.elements.start.disabled=full;
            if(full){f.elements.start.value='09:00';f.elements.end.value='17:00';f.elements.window.value=w.arrival_windows[0];}
            else{const [h,m]=f.elements.start.value.split(':').map(Number),minutes=h*60+m+Number(f.elements.duration.value)*60;f.elements.end.value=String(Math.floor(minutes/60)).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0');}
            const contact=needsContact||f.elements.window.value!==a.requested_window;
            f.querySelector('.booking-contact').style.display=contact?'':'none';f.elements.client_confirmed.required=contact;f.elements.contact_category.required=contact;
          };
          const setTimes=()=>{f.elements.start.value=f.elements.window.value.startsWith('12:')?'12:00':'09:00';durationChanged();};setTimes();
          f.elements.window.onchange=setTimes;f.elements.duration.onchange=durationChanged;f.elements.start.addEventListener('change',durationChanged);
          f.elements.subcontractor.required=true;
          installBookingTimePicker(f.elements.start,'Choose booking start time');
          f.onsubmit=async e=>{e.preventDefault();const v=Object.fromEntries(new FormData(f)),button=f.querySelector('[type=submit]'),error=f.querySelector('[role=alert]');button.disabled=true;error.hidden=true;
            try{const selectedPrevious=f.elements.replace_visit?previousBookings.find(row=>String(row.id)===f.elements.replace_visit.value):previousBooking;const old=adding?null:a.appointment_id?{id:a.appointment_id}:selectedPrevious?{id:selectedPrevious.appointment_id}:null;const body={version:job.version,attendance:a.id,date:v.date,window:f.elements.window.value,client_confirmed:f.elements.client_confirmed?.checked||false,contact_category:v.contact_category||'',subcontractor:v.subcontractor,phone_confirmed:true,add_appointment:adding,duration:f.elements.duration.value,starts_at:v.date+'T'+f.elements.start.value+':00+02:00',ends_at:v.date+'T'+f.elements.end.value+':00+02:00'};if(replacing)body.replace_cancelled=a.appointment_id;if(old)body.appointment=old.id;if(v.reason)body.reason=v.reason;if(v.override_reason)body.override_reason=v.override_reason;
              await api(`requests/${job.id}/workflow/confirm-attendance/`,{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(body)});showDetail(await api(`requests/${job.id}/`));
            }catch(e){error.hidden=false;error.textContent=e.message;error.scrollIntoView({block:'nearest'});}finally{if(button.isConnected)button.disabled=false;}
          };
          container.scrollIntoView({block:'nearest'});
        }catch(e){if(container.dataset.generation===generation)container.innerHTML=`<p role="alert">${esc(e.message)}</p>`;}
      });
    }

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
  return {icon,categoryIcon,categoryDescription,navIcon,decorate,stages,inbox,job,agencies,photoPicker};
})();
