// Optional browser smoke test. Uses an existing Playwright installation.
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/home/michael/.cache/ms-playwright-go/1.50.1/package');
(async () => {
  const report = path.resolve(process.argv[2] || 'optimizer/runs/dashboard/index.html');
  const browser = await chromium.launch({executablePath:process.env.CHROME_BIN || '/opt/google/chrome/chrome',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1500,height:1100}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route(/^https?:/, r => r.abort());
    await page.goto(pathToFileURL(report).href);
    assert.deepEqual(errors, []);
    assert.match(await page.title(), /Gowin Workbench/);
    assert.ok(await page.locator('#builds tr').count() >= 3);
    await page.locator('#filter').fill('console_neo_n18');
    await page.locator('#builds tr').filter({hasText:'TIMING_FAIL'}).first().click();
    assert.equal(await page.locator('#name').innerText(), 'console_neo_n18');
    assert.match(await page.locator('#pathSummary').innerText(), /row_offset/);
    assert.match(await page.locator('#pathSummary').innerText(), /Charge maximale/);
    assert.match(await page.locator('#pathSummary').innerText(), /Piste à tester/);
    assert.ok(await page.locator('#clockRoutes tr').count() > 0);
    assert.match(await page.locator('#clockScope').innerText(), /ne prouve pas/);
    const map = await page.locator('#map').boundingBox();
    await page.mouse.move(map.x+100, map.y+100);
    await page.mouse.down();
    await page.mouse.move(map.x+220, map.y+220);
    await page.mouse.up();
    assert.match(await page.locator('#region').inputValue(), /^R\[\d+:\d+\]C\[\d+:\d+\]$/);
    await page.locator('#proposal').click();
    assert.match(await page.locator('#command').innerText(), /optimize.py place/);
    await page.locator('#pathSelect').selectOption('1');
    assert.ok(await page.locator('#arcs tr').count() > 0);
    // Optional evidence-enabled fixture: timing must remain visible beside
    // the physical failure, never replaced with a reassuring overall PASS.
    await page.locator('#filter').fill('console_neo_n21r1');
    if (await page.locator('#builds tr').count()) {
      const row = page.locator('#builds tr').first();
      await row.click();
      assert.match(await row.innerText(), /TIMING_PASS/);
      const evidence = await page.locator('#boardEvidence').innerText();
      if (!evidence.includes('Non testé')) {
        assert.match(evidence, /Échec de l’essai/);
        assert.match(await row.innerText(), /Échec/);
        assert.match(await page.locator('#boardScope').innerText(), /pas une validation complète/);
      }
    }
    await page.locator('#filter').fill('neo_probe');
    await page.locator('#builds tr').first().click();
    assert.equal(await page.locator('#proposal').isDisabled(), true);
    await page.locator('#filter').fill('');
    await page.screenshot({path:path.join(path.dirname(report),'screenshot.png'),fullPage:true});
    assert.deepEqual(errors, []);
    await page.setViewportSize({width:430,height:900});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    const result = {passed:true, browser:await browser.version(), errors, report};
    fs.writeFileSync(path.join(path.dirname(report),'browser-test.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1});
