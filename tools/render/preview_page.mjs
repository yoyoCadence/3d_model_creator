// Screenshot site/index.html locally (desktop + phone) the way the artifact will render it.
// Usage: THREE_DIR=... node tools/render/preview_page.mjs outDir
import { spawn } from 'node:child_process';
import path from 'node:path';
import { createRequire } from 'node:module';

const { chromium } = createRequire(import.meta.url)('playwright');
const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
const out = process.argv[2];
const srv = spawn('node', [path.join(ROOT, 'tools/render/shoot.mjs'), '/dev/null', '--serve'], { env: process.env });
const url = await new Promise((res) => srv.stdout.on('data', (d) => res(String(d).trim())));
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
for (const [name, vp, scheme] of [['desktop', { width: 1280, height: 900 }, 'light'], ['phone', { width: 400, height: 860 }, 'dark']]) {
  const page = await browser.newPage({ viewport: vp, colorScheme: scheme });
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await page.route('https://cdn.jsdelivr.net/npm/three@0.170.0/**', (route) => {
    route.fulfill({ path: path.join(process.env.THREE_DIR, route.request().url().split('three@0.170.0/')[1]), contentType: 'text/javascript' });
  });
  await page.route('https://fonts.googleapis.com/**', (r) => r.fulfill({ body: '', contentType: 'text/css' }));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForTimeout(25000);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  await page.screenshot({ path: path.join(out, `page_${name}.png`), fullPage: true });
  console.log(name, 'overflowX=', overflow, 'errors=', JSON.stringify(errs.slice(0, 5)));
}
await browser.close();
srv.kill();
