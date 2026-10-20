/* Invoked by Django's optional browser test with isolated test sessions on stdin. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  const {url, sessions} = JSON.parse(input);
  const browser = await chromium.launch({headless:true,
    ...(process.env.SEVLINK_CHROMIUM_PATH ? {executablePath:process.env.SEVLINK_CHROMIUM_PATH} : {}), args:['--no-sandbox']});
  const errors = [], failedAssets = [];
  const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAFElEQVR4nGNkYPjPAANMDEgANwcAMdMBB1sLEtoAAAAASUVORK5CYII=', 'base64');
  let downloadUrl;
  try {
    async function signedIn(role, width = 1440) {
      const context = await browser.newContext({viewport:{width,height:900}});
      await context.addCookies([{name:'sessionid', value:sessions[role], url}]);
      const page = await context.newPage();
      page.setDefaultTimeout(10000);
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => {if (response.url().includes('/static/') && response.status() >= 400) failedAssets.push(response.url());});
      await page.goto(url + '/maintenance/');
      await page.getByRole('button', {name:'Repair jobs', exact:false}).waitFor();
      assert.equal(await page.locator('#role').count(), 0, 'No simulated role picker');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No page overflow');
      return {context, page};
    }
    let {context, page} = await signedIn('tenant', 390);
    await page.locator('#phoneNav [data-view=report]').click();
    await page.locator('[data-category="Plumbing"]').click();
    await page.locator('[name=title]').fill('Kitchen tap leaking');
    await page.locator('[name=description]').fill('The kitchen tap drips after it is turned off.');
    await page.locator('#reportForm [name=attachments]').setInputFiles({name:'repair.png', mimeType:'image/png', buffer:image});
    await page.getByRole('button', {name:'Send report to property manager'}).click();
    await page.getByRole('button', {name:'Open job'}).waitFor();
    await page.getByRole('button', {name:'Open job'}).click();
    await page.locator('#jobcontent').getByText('Awaiting property manager review').waitFor();
    downloadUrl = await page.locator('#modal .file a').first().getAttribute('href');
    assert.equal((await page.request.get(new URL(downloadUrl, url).href)).status(), 200);
    await page.locator('#commentForm [name=text]').fill('Please call before visiting.');
    await page.getByRole('button', {name:'Add comment', exact:true}).click();
    await page.locator('.comment').filter({hasText:'Please call before visiting.'}).waitFor();
    assert.equal(await page.locator('#statusForm').count(), 0);
    assert.equal(await page.evaluate(() => indexedDB.databases().then(dbs => dbs.length)), 0, 'Live mode does not use demo IndexedDB');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.getByRole('button', {name:'Close', exact:true}).click();
    await page.getByRole('button', {name:'Sign out', exact:true}).click();
    await page.waitForURL('**/login/');
    await context.close();

    ({context, page} = await signedIn('pm'));
    await page.getByRole('button', {name:'Open job'}).click();
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#modal .file a').first().click();
    const downloaded = await downloadEvent;
    assert.equal(downloaded.suggestedFilename(), 'repair.png');
    assert.equal(await downloaded.failure(), null);
    await page.locator('#attachmentForm [name=attachments]').setInputFiles({name:'followup.png', mimeType:'image/png', buffer:image});
    await page.getByRole('button', {name:'Upload attachments', exact:true}).click();
    await page.locator('#modal .file').nth(1).waitFor();
    await page.locator('[name=status]').selectOption('reviewed');
    await page.getByRole('button', {name:'Save status'}).click();
    await page.locator('#jobcontent .activity').filter({hasText:'Reviewed'}).waitFor();
    await context.close();

    // The logout invalidated the original tenant session. Obtain another authenticated
    // session via the test-only Django fixture, never via a production backdoor.
    // Reuse a fresh browser with a second pre-created test login below.
    ({context, page} = await signedIn('tenantAgain', 390));
    await page.getByRole('button', {name:'Open job'}).click();
    await page.locator('#jobcontent .activity').filter({hasText:'Reviewed'}).waitFor();
    assert.equal(await page.locator('#statusForm').count(), 0);
    assert.equal(await page.locator('#modal').innerText().then(t => /internal_notes|subcontractor/i.test(t)), false);
    await context.close();

    ({context, page} = await signedIn('foreign'));
    assert.equal((await page.request.get(new URL(downloadUrl, url).href)).status(), 404);
    assert.equal(await page.locator('#modal .file').count(), 0);
    await context.close();

    ({context, page} = await signedIn('superadmin'));
    await page.getByRole('button', {name:'Open job'}).click();
    await page.locator('#jobcontent .activity').filter({hasText:'Reviewed'}).waitFor();
    assert.equal((await page.request.get(new URL(downloadUrl, url).href)).status(), 200);
    await page.locator('#quoteForm [name=title]').fill('Browser quotation');
    await page.locator('#quoteForm [name=scope]').fill('Replace kitchen tap and test.');
    await page.locator('#quoteForm [name=amount]').fill('1250.00');
    await page.getByRole('button', {name:'Issue quotation', exact:true}).click();
    await page.locator('.card h2').filter({hasText:'Browser quotation'}).waitFor();
    await context.close();

    ({context, page} = await signedIn('pm'));
    const jobId = new URL(downloadUrl, url).pathname.split('/')[4];
    await page.goto(url + '/maintenance/?job=' + jobId);
    await page.locator('.quoteDecision').waitFor();
    await page.locator('.quoteDecision [name=status]').selectOption('approved');
    await page.getByRole('button', {name:'Save quotation decision', exact:true}).click();
    await page.locator('.card .badge').filter({hasText:'approved'}).waitFor();
    await page.locator('#commentForm [name=text]').fill('Approved. Please coordinate access.');
    await page.getByRole('button', {name:'Add comment', exact:true}).click();
    await page.locator('.comment').filter({hasText:'Approved. Please coordinate access.'}).waitFor();
    await context.close();
    assert.deepEqual(errors, []); assert.deepEqual(failedAssets, []);
    console.log('PASS: real browser tenant photo/report upload, authenticated PM download and follow-up upload, cross-agency download denial, database persistence, PM status update, logout/new tenant session, superadmin quote issue, authorized PM approval and saved tenant/PM comments, secure deep link, mobile layout, CSRF, no demo role switch or IndexedDB.');
  } finally { await browser.close(); }
});
