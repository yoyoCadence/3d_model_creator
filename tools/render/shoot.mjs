// Headless screenshots of GLB models through site/render.html (same viewer as the HTML page).
// Usage: node tools/render/shoot.mjs jobs.json
//   jobs.json = [{ "model": "assets/...glb", "out": "assets/renders/x.png", "preset": "studio",
//                  "view": "front", "w": 800, "h": 1000, "height": 1.8, "yaw": 0, "debug": "lit" }, ...]
// three.js is served from a local node_modules (THREE_DIR env) instead of the CDN.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

// playwright is installed globally in this environment; createRequire honours NODE_PATH/global dirs
const { chromium } = createRequire(import.meta.url)('playwright');

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
const THREE_DIR = process.env.THREE_DIR;
if (!THREE_DIR) throw new Error('set THREE_DIR=/path/to/node_modules/three');
const jobs = process.argv[3] === '--serve' ? [] : JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.png': 'image/png', '.json': 'application/json', '.txt': 'text/plain' };

// Serves the repo root, falling back to site/ (so /index.html, /js, /data resolve like the published page).
// Artifact pages are fragments without <!doctype>; wrap them like the publisher does.
const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let p = path.join(ROOT, rel);
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) p = path.join(ROOT, 'site', rel === '/' ? 'index.html' : rel);
  if (!p.startsWith(ROOT) || !fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' });
  if (p.endsWith('.html')) {
    const html = fs.readFileSync(p, 'utf8');
    return res.end(/<!doctype/i.test(html) ? html
      : `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>${html}</body></html>`);
  }
  fs.createReadStream(p).pipe(res);
}).listen(0);
if (process.argv[3] === '--serve') { console.log(`http://127.0.0.1:${server.address().port}/`); await new Promise(() => {}); }
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1600 } });
page.on('pageerror', (e) => console.error('pageerror', e.message));
await page.route('https://cdn.jsdelivr.net/npm/three@0.170.0/**', (route) => {
  const rel = route.request().url().split('three@0.170.0/')[1];
  route.fulfill({ path: path.join(THREE_DIR, rel), contentType: 'text/javascript' });
});

const results = [];
for (const j of jobs) {
  const q = new URLSearchParams(j.model ? { ...j, model: '/' + j.model } : j);
  q.delete('out');
  q.delete('page');
  await page.goto(`http://127.0.0.1:${port}/site/${j.page || 'render.html'}?${q}`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 180000 });
  const err = await page.evaluate(() => window.__error);
  if (err) { console.error(j.model, err); results.push({ ...j, error: err }); continue; }
  const stats = await page.evaluate(() => window.__stats);
  const outPath = path.isAbsolute(j.out) ? j.out : path.join(ROOT, j.out);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  await page.locator('#c').screenshot({ path: outPath });
  console.log('ok', j.out, JSON.stringify(stats));
  results.push({ ...j, stats });
}
await browser.close();
server.close();
fs.writeFileSync(process.argv[2].replace(/\.json$/, '.out.json'), JSON.stringify(results, null, 2));
