const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
(async () => {
  const qs = process.argv.slice(2);
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 1000 }, locale: 'ko-KR' });
  const pg = await ctx.newPage();
  const out = [];
  for (const [i, q] of qs.entries()) {
    await pg.goto('https://search.naver.com/search.naver?query=' + encodeURIComponent(q), { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(e => out.push({ q, err: e.message }));
    await pg.waitForTimeout(2500);
    const info = await pg.evaluate(() => {
      const hits = [...document.querySelectorAll('a[href*="gangsanjawon.com"]')];
      const res = hits.map(a => {
        const r = a.getBoundingClientRect();
        let box = a.closest('li, .bx, .total_wrap, .fds-web-doc-root, section, div[class*="item"]') || a;
        const sec = a.closest('section, .api_subject_bx, .sc_new');
        const h = sec ? (sec.querySelector('h2, .api_title, .fds-comps-header-headline')||{}).innerText : '';
        return { href: a.href, text: (a.innerText||'').trim().slice(0,80), y: Math.round(r.top + scrollY), section: (h||'').trim().slice(0,40) };
      });
      const title = document.title;
      const captcha = /자동입력|보안|captcha|비정상/i.test(document.body.innerText.slice(0,2000));
      return { res, title, captcha };
    });
    out.push({ q, ...info });
    if (info.res.length) {
      const y = Math.max(0, info.res[0].y - 250);
      await pg.evaluate(y => window.scrollTo(0, y), y);
      await pg.waitForTimeout(800);
      await pg.screenshot({ path: (process.env.SHOT_DIR || ".") + `/${i}.png` });
    }
    await pg.waitForTimeout(3000 + Math.random() * 2000);
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
