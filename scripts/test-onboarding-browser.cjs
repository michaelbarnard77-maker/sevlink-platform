/* A real password-based first-account journey; no injected authenticated sessions. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
let input='';process.stdin.on('data',chunk=>input+=chunk);
process.stdin.on('end',async()=>{
  const {url,verificationToken,invitationToken}=JSON.parse(input);
  const browser=await chromium.launch({headless:true,...(process.env.SEVLINK_CHROMIUM_PATH?{executablePath:process.env.SEVLINK_CHROMIUM_PATH}:{}),args:['--no-sandbox']});
  try {
    const owner=await browser.newContext(), tenant=await browser.newContext();
    const p=await owner.newPage(), t=await tenant.newPage();
    const password='Browser-acceptance-password-482!';
    await p.goto(url+'/register/');
    for(const [name,value] of Object.entries({agency_name:'Acceptance Agency',first_name:'Agency Owner',email:'browser-owner@example.test',phone:'0000000000',area:'Gauteng and Cape Town',password1:password,password2:password})) await p.locator(`[name=${name}]`).fill(value);
    await p.getByRole('button',{name:'Save & continue'}).click();
    await p.getByRole('heading',{name:'Verify your email'}).waitFor({timeout:5000}).catch(async error=>{throw new Error(error.message+'\nPage: '+await p.locator('body').innerText());});
    // Synthetic local tokens are supplied by the Python test, never a live mailbox.
    await p.goto(url+'/invitation/'+verificationToken+'/');
    await p.getByRole('button',{name:'Verify & open workspace'}).click();
    await p.locator('#nav [data-view=properties]').click();
    await p.getByRole('link',{name:'Add Property',exact:false}).click();
    for(const [name,value] of Object.entries({name:'Acceptance Home',address:'Synthetic Cape Town address'})) await p.locator(`[name=${name}]`).fill(value);
    await p.getByRole('button',{name:'Save & continue'}).click();
    await p.locator('#nav [data-view=properties]').click();
    await p.getByRole('link',{name:'Link Tenant'}).click();
    await p.locator('[name=name]').fill('Acceptance Tenant');
    await p.locator('[name=email]').fill('browser-tenant@example.test');
    await p.getByRole('button',{name:'Save & continue'}).click();
    await t.goto(url+'/invitation/'+invitationToken+'/');
    await t.locator('[name=new_password1]').fill(password);await t.locator('[name=new_password2]').fill(password);
    await t.getByRole('button',{name:'Create my account'}).click();
    await t.getByText('Synthetic Cape Town address',{exact:true}).waitFor();
    await t.getByRole('link',{name:'Maintenance Requests'}).click();
    await t.getByRole('button',{name:'My Repairs',exact:false}).waitFor();
    assert.equal(await t.locator('#role').count(),0);
    await t.getByRole('button',{name:'Sign out',exact:true}).click();
    await t.waitForURL('**/login/');
    await t.locator('[name=username]').fill('browser-tenant@example.test');await t.locator('[name=password]').fill(password);
    await t.getByRole('button').click();
    await t.getByText('Synthetic Cape Town address',{exact:true}).waitFor();
    assert.equal(await t.getByRole('link',{name:'Manage account access'}).count(),0);
    await p.goto(url+'/maintenance/');await p.locator('#nav [data-view=profile]').click();
    await p.getByRole('link',{name:'Manage account access'}).click();
    await p.getByRole('link',{name:'Record move-out'}).click();
    await p.locator('[name=reason]').fill('Synthetic acceptance move-out');await p.locator('[name=confirm]').check();
    await p.getByRole('button',{name:'Save & continue'}).click();
    await t.reload();assert.equal(await t.getByText('Synthetic Cape Town address',{exact:true}).count(),0);
    await owner.close();await tenant.close();
    process.stdout.write('PASS: fresh registration, verification, invitation, tenant password login and audited move-out.\n');
  } finally {await browser.close();}
});
