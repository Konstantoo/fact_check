// Рендер инфографики в PNG: node render.mjs
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
const dir = path.dirname(fileURLToPath(import.meta.url));
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const page = await browser.newPage({ viewport: { width: 1080, height: 800 }, deviceScaleFactor: 2 });
await page.goto('file://' + path.join(dir, 'index.html'));
await page.waitForTimeout(300);
await page.screenshot({ path: path.join(dir, 'infographic.png'), fullPage: true });
await browser.close();
console.log('saved infographic.png');
