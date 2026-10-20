const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const modal={open:false,querySelector:()=>null,querySelectorAll:()=>[],insertAdjacentHTML(){},close(){this.open=false}},app={innerHTML:'',querySelector:()=>null,querySelectorAll:()=>[]};
const context=vm.createContext({console,crypto:webcrypto,structuredClone,Date,Intl,setTimeout,clearTimeout,document:{querySelector:s=>s==='#app'?app:s==='#modal'?modal:null,addEventListener(){}}});
const html=fs.readFileSync('dist/index.html','utf8');
for(const [,file]of html.matchAll(/<script src="([^"]+)"/g))vm.runInContext(fs.readFileSync('dist/'+file,'utf8').replace(/^startup\(\);/m,''),context,{filename:file});
async function run(code){return vm.runInContext('(async()=>{'+code+'})()',context)}
(async()=>{
// Use the real commit/enrichment chain, replacing browser persistence and UI with memory-only adapters.
await run(`state=initialDemoState();normalise();persist=async()=>{};render=()=>{};jobDetail=()=>{};toast=()=>{};agency='test-agency';activeMember='admin';tenant='test-tenant';role='tenant';await commit(()=>{state.agencies.push({id:agency,name:'Test Agency',contact:'Agency Admin',email:'agency@example.test'});state.members.push({id:'test-pm',agency,name:'Test PM'});state.properties.push({id:'test-property',agency,manager:'test-pm',name:'Unit 12',address:'12 Test Road'});state.tenants.push({id:tenant,agency,property:'test-property',name:'Test Tenant'});state.subbies.push({id:'test-partner',name:'PRIVATE PARTNER',trade:'Plumbing'})});`);
assert.equal(await run(`return submitTenantReport({property:'test-property',category:'Plumbing',title:'Leaking tap',description:'The kitchen tap has been dripping since yesterday.'})`),true);
assert.equal(await run('return jobStatusLabel(state.jobs[0])'),'Awaiting property manager review');
await run("flowJobId=state.jobs[0].id;role='sevlink'");assert.equal(await run('return getJob(flowJobId)'),undefined);
await run("role='manager'");assert.equal(await run(`return dispatchTenantReport(flowJobId,{title:'Kitchen tap leaking',description:'Inspect and repair the kitchen mixer.',service:'repair',priority:'Normal',accessResponsibility:'sevlink',access:'Call the tenant'})`),true);
await run("role='sevlink';await routeQuoting(flowJobId)");assert.equal(await run('return jobStage(getJob(flowJobId))'),'quoting');
// Capture the actual upload-quote form callback and provide a supported document fixture.
await run(`openForm=(title,content,submit,handler)=>{capturedQuoteHandler=handler};fileData=async()=>({name:'Sevlink-quote.pdf',type:'application/pdf',data:'data:application/pdf;base64,JVBERg=='});quoteForm(flowJobId);await capturedQuoteHandler(new Map([['supplier','Sevlink'],['amount','4000'],['scope','Replace and test the kitchen mixer.'],['file',{}]]));`);
assert.equal(await run('return jobStage(getJob(flowJobId))'),'approval');
await run("role='manager';await approve(flowJobId,getJob(flowJobId).quotes[0].id)");
await run("role='sevlink'");assert.equal(await run('return jobStage(getJob(flowJobId))'),'deposit');
const booking="{job:flowJobId,subbie:'test-partner',when:'2031-01-06T10:00',duration:120,price:650,instructions:'PRIVATE INSTRUCTIONS',internalNote:'PRIVATE COST NOTE',clientNote:'Please allow access to the kitchen.',confirmBooking:true,agreed:true}";
assert.equal(await run(`return savePrivateBooking('',${booking})`),false);
assert.equal(await run(`return !!await saveSingleJobInvoice(flowJobId,{number:'INV-TEST-100',issueDate:todayKey(),dueDate:todayKey(),billTo:'Test Agency',email:'agency@example.test',requestedAmount:2000,file:{name:'INV-TEST-100.pdf',type:'application/pdf',data:'data:application/pdf;base64,JVBERg=='}})`),true);
assert.equal(await run('return getJob(flowJobId).companyInvoiceNumber'),'INV-TEST-100');
const payment=(amount,purpose,verified)=>`{amount:${amount},date:todayKey(),reference:'SAME-BANK-REFERENCE',purpose:'${purpose}',verified:${verified},pop:{name:'pop.pdf',type:'application/pdf',data:'data:application/pdf;base64,JVBERg=='}}`;
await run("flowInvoiceId=getJob(flowJobId).invoices[0].id;role='manager'");
assert.equal(await run(`return recordClientPayment(flowJobId,flowInvoiceId,${payment(1000,'Deposit',true)})`),true);
assert.equal(await run('return getJob(flowJobId).invoices[0].payments[0].verification'),'Pending');
await run("role='sevlink'");assert.equal(await run('return verifyClientPayment(flowJobId,flowInvoiceId,getJob(flowJobId).invoices[0].payments[0].id,true)'),true);
assert.equal(await run('return depositSummary(getJob(flowJobId)).outstanding'),1000);
assert.equal(await run(`return savePrivateBooking('',${booking})`),false);
assert.equal(await run(`return recordClientPayment(flowJobId,flowInvoiceId,${payment(1000,'Payment',true)})`),true);
assert.equal(await run('return jobStage(getJob(flowJobId))'),'scheduling');
assert.equal(await run(`return savePrivateBooking('',${booking})`),true);
assert.equal(await run('return jobStatusLabel(getJob(flowJobId))'),'Appointment booked');
await run("role='tenant'");assert.equal(await run("return confirmAccess(flowJobId,'I will be home to provide access.')"),true);
assert.equal(await run('return JSON.stringify(getJob(flowJobId).schedule).includes("PRIVATE")'),false);
await run("role='sevlink'");assert.equal(await run('return markJobOnSite(flowJobId)'),true);
assert.equal(await run('return finishVisit(flowJobId,{outcome:"completed",notes:"Mixer replaced and tested. No leaks.",checks:"Water pressure and seals checked."})'),true);
assert.equal(await run('return jobStage(getJob(flowJobId))'),'invoicing');
assert.equal(await run(`return !!await saveSingleJobInvoice(flowJobId,{number:'INV-TEST-100',issueDate:todayKey(),dueDate:todayKey(),billTo:'Test Agency',email:'agency@example.test',requestedAmount:2000,file:null})`),true);
assert.equal(await run('return getJob(flowJobId).invoices.length'),1);
assert.equal(await run('return invoiceBalance(getJob(flowJobId).invoices[0])'),2000);
assert.equal(await run('return jobStage(getJob(flowJobId))'),'payment');
assert.equal(await run(`return recordClientPayment(flowJobId,flowInvoiceId,${payment(2000,'Balance',true)})`),true);
assert.equal(await run('return jobStage(getJob(flowJobId))'),'closed');
assert.equal(await run('return invoiceState(getJob(flowJobId).invoices[0])'),'Paid');
assert.equal(await run('return getJob(flowJobId).companyInvoiceNumber'),'INV-TEST-100');
assert.equal(await run('return reportMarkup(getJob(flowJobId)).includes("PRIVATE")'),false);
assert.equal(await run('return professionalInvoiceEmailMarkup(getJob(flowJobId),getJob(flowJobId).invoices[0]).includes("PRIVATE")'),false);
assert.equal(await run('return reportMarkup(getJob(flowJobId)).includes(sevlinkLegalName)'),true);
assert.equal(await run('return professionalQuoteMarkup(getJob(flowJobId),getJob(flowJobId).quotes[0]).includes("12 Test Road")'),true);
// The lock prevents duplicate submissions while a slow save is in progress, and releases after failure.
await run(`submitCalls=0;mockForm={dataset:{},isConnected:true,button:{disabled:false,textContent:'Save'},setAttribute(){},removeAttribute(){},querySelector(){return this.button}};guardedSubmit=submissionGuard(mockForm,async()=>{submitCalls++;await new Promise(resolve=>releaseSave=resolve)});firstSubmit=guardedSubmit({preventDefault(){}});await guardedSubmit({preventDefault(){}});`);
assert.equal(await run('return submitCalls'),1);assert.equal(await run('return mockForm.button.disabled'),true);
await run('releaseSave();await firstSubmit');assert.equal(await run('return mockForm.button.disabled'),false);
await run(`failedSubmit=submissionGuard(mockForm,async()=>{throw Error('test failure')});try{await failedSubmit({preventDefault(){}})}catch{};`);assert.equal(await run('return mockForm.dataset.saving'),'false');
console.log('PASS: real commit chain from tenant report → PM review → uploaded quote → approval → partial deposit + top-up → booking → tenant access → on site → completion → final balance request → paid/closed, with one locked invoice number. Document privacy and concurrent-submit guards also passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
