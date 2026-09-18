// Рендер инфографики в PNG: python3 build.py && node render.mjs
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
const dir = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 2 });
for (const [html, png] of [['part1.html','infographic-1.png'],['part2.html','infographic-2.png']]) {
  await page.goto('file://' + path.join(dir, html));
  await page.waitForTimeout(200);
  await page.locator('.page').screenshot({ path: path.join(dir, png) });
  console.log('saved', png);
}
await browser.close();
