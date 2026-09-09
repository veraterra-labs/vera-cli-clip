// Copyright (c) 2026 Tsuyoshi Hemmi / License: MIT
// フレームHTMLを 1920x1080 で録画→webm（cli-clip 版）。使い方: node cap_frame.mjs <htmlFile> <outDir> [w] [h] [query]
// playwright はスキル直下の node_modules から読む（cli-clip-setup が `npm install` する）。
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, '..', 'package.json'));
const { chromium } = require('playwright');

const [htmlFile, outDir, wArg, hArg, query] = process.argv.slice(2);
const W = +(wArg||1920), H = +(hArg||1080);
const HTML = path.isAbsolute(htmlFile) ? htmlFile : path.join(here, htmlFile);
const Q = query ? (query.startsWith('?') ? query : '?'+query) : '';

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: W, height: H },
  recordVideo: { dir: outDir, size: { width: W, height: H } },
  deviceScaleFactor: 1,
});
const page = await ctx.newPage();
await page.goto(`file://${HTML}${Q}`);
await page.waitForFunction(() => window.__done === true, { timeout: 120000 });
await page.waitForTimeout(800);
const beatAt = await page.evaluate(() => window.__beatAt || 0);
const video = page.video();
await ctx.close();
const p = await video.path();
console.log('VIDEO:' + p);
console.log('BEAT:' + beatAt);
await browser.close();
