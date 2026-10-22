const {chromium}=require('playwright');const assert=require('node:assert/strict');
let input='';process.stdin.on('data',c=>input+=c);process.stdin.on('end',async()=>{
 const {url,sessions,week}=JSON.parse(input);const browser=await chromium.launch({headless:true,...(process.env.SEVLINK_CHROMIUM_PATH?{executablePath:process.env.SEVLINK_CHROMIUM_PATH}:{}),args:['--no-sandbox']});const errors=[];
 try{
  async function signed(role,width=1440){const c=await browser.newContext({viewport:{width,height:950}});await c.addCookies([{name:'sessionid',value:sessions[role],url}]);const p=await c.newPage();p.setDefaultTimeout(10000);p.on('pageerror',e=>errors.push(e.message));await p.goto(url+'/maintenance/');await p.locator('#attention').waitFor();return {c,p};}
  let {c,p}=await signed('pm');
  await p.locator('#workflowStages .stage-card').first().waitFor();
  assert.deepEqual(await p.locator('#workflowStages .stage-card b').allTextContents(),['Needs Your Attention','New Requests','Awaiting Quote Approval','Awaiting Deposit','Booked','Work Underway','Awaiting Final Payment','Closed']);
  assert(await p.evaluate(()=>document.querySelector('#attention').compareDocumentPosition(document.querySelector('#workflowStages')) & Node.DOCUMENT_POSITION_FOLLOWING));
  const dashboard=await (await p.request.get(url+'/api/maintenance/workflow/stages/')).json();
  const attention=await (await p.request.get(url+'/api/maintenance/portal/attention/')).json();
  assert.equal(dashboard.stages[0].count,new Set(attention.items.map(a=>a.job)).size);
  await p.locator('[data-stage=attention]').click();
  await p.locator('#stageJobs h2').waitFor();
  assert.equal(await p.locator('#stageJobs [data-stage-job]').count(),dashboard.stages[0].count);
  assert.deepEqual(await p.locator('#nav button').allTextContents(),['Overview','Report a Repair','Repair Jobs','Properties','Tenants','Quotations','Accounts & Payments','Maintenance Calendar','Updates & Notifications','Agency Profile','Report Website Issue']);
  assert.equal(await p.getByText('Account & properties',{exact:true}).count(),0);
  await p.locator('#attention .attention-card').filter({hasText:'Review new maintenance request'}).filter({hasText:'GP repair'}).getByRole('button',{name:'Review job'}).click();
  await p.getByRole('tab',{name:'Activity / Timeline',exact:true}).click();await p.locator('#statusForm [name=status]').selectOption('reviewed');await p.locator('#statusForm button').click();await p.locator('#jobcontent').getByText('Reviewed',{exact:false}).waitFor();await p.getByRole('button',{name:'Close',exact:true}).click();
  await p.locator('#attention .attention-card').filter({hasText:'GP repair'}).filter({hasText:'Review new maintenance request'}).waitFor({state:'detached'});
  await p.locator('#nav [data-view=accounts]').click();await p.locator('#accountFilter').selectOption('overdue');await p.locator('.attention-card').filter({hasText:'CUSTOMER-PDF-001'}).waitFor();
  assert(/1[^0-9]?000[.,]00/.test(await p.locator('#app').textContent()));
  const file=p.locator('#app a').filter({hasText:'Download invoice PDF'});assert.equal((await p.request.get(url+await file.getAttribute('href'))).status(),200);
  assert.equal(await p.locator('.invoicePayment').count(),0);
  // An older invoice response must not overwrite a newer navigation/filter choice.
  let hold=true,release,started;const held=new Promise(resolve=>release=resolve),ready=new Promise(resolve=>started=resolve);
  let heldRequest;
  const delay=async route=>{if(hold && new URL(route.request().url()).searchParams.get('filter')==='unpaid'){hold=false;heldRequest=route.request();const response=await route.fetch();started();await held;await route.fulfill({response});}else await route.continue();};
  await p.route('**/api/maintenance/portal/accounts/**',delay);
  await p.locator('#accountFilter').selectOption('unpaid');await ready;
  await p.locator('#nav [data-view=properties]').click();await p.locator('#app').getByText('Original Gauteng address',{exact:true}).waitFor();
  await p.locator('#nav [data-view=accounts]').click();await p.locator('#accountFilter').waitFor();await p.locator('#accountFilter').selectOption('paid');
  await p.getByText('No invoices match this filter.',{exact:true}).waitFor();
  const finished=p.waitForEvent('requestfinished',{predicate:r=>r===heldRequest});release();await finished;
  await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await p.locator('#accountFilter').inputValue(),'paid');assert.equal(await p.locator('#app .attention-card').count(),0);
  await p.unroute('**/api/maintenance/portal/accounts/**',delay);

  await p.locator('#nav [data-view=quotes]').click();await p.locator('#app').getByRole('button',{name:'Open quotation'}).click();await p.getByRole('tab',{name:'Quotations',exact:true}).click();await p.locator('.quoteDecision [name=reason]').fill('Browser approval');await p.locator('.quoteDecision button').click();await p.locator('.card .badge').filter({hasText:'approved'}).waitFor();await p.getByRole('button',{name:'Close',exact:true}).click();
  await p.locator('#nav [data-view=publicCalendar]').click();await p.locator('#customerWeek').fill(week);await p.locator('#customerWeek').dispatchEvent('change');await p.locator('.customer-week .attention-card').waitFor();
  const calendar=await p.locator('.customer-week').textContent();assert(calendar.includes('scheduled'));for(const privateValue of ['PRIVATE','Team A','commission','subcontractor'])assert(!calendar.includes(privateValue));
  await p.locator('#nav [data-view=properties]').click();await p.locator('#app').getByText('Original Gauteng address',{exact:true}).waitFor();
  await p.locator('#nav [data-view=tenants]').click();await p.locator('#app').getByRole('heading',{name:'Test tenant'}).waitFor();
  await p.locator('#nav [data-view=profile]').click();await p.locator('#app').getByRole('heading',{name:'Regional agency'}).waitFor();
  await p.locator('#nav [data-view=updates]').click();await p.getByRole('heading',{name:'Updates & Notifications'}).waitFor();
  await p.locator('#nav [data-view=issues]').click();await p.locator('#websiteIssue [name=subject]').fill('Synthetic portal issue');await p.locator('#websiteIssue [name=description]').fill('Synthetic screenshot-free report');await p.locator('#websiteIssue button').click();await p.locator('#app').getByRole('heading',{name:'Synthetic portal issue'}).waitFor();await c.close();
  ({c,p}=await signed('tenant',390));assert.equal(await p.locator('#nav [data-view=accounts]').count(),0);assert.equal(await p.locator('#nav [data-view=quotes]').count(),0);
  await p.locator('#phoneNav [data-view=publicCalendar]').click();await p.locator('#customerWeek').fill(week);await p.locator('#customerWeek').dispatchEvent('change');await p.locator('.customer-week .attention-card').waitFor();
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal((await p.request.get(url+'/api/maintenance/portal/accounts/')).status(),403);
  assert.equal((await p.request.get(url+'/api/maintenance/operations/monday-payments/')).status(),403);
  await c.close();assert.deepEqual(errors,[]);process.stdout.write('PASS: scoped PM attention, review/approval resolution, invoices/PDF, real navigation, shared calendar, tenant mobile/privacy and saved website reports.\n');
 }finally{await browser.close();}
});
