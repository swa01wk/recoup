#!/usr/bin/env node
/**
 * Renders Builder cover HTML at 1200×675 → PNG.
 *
 * Usage (from repo root):
 *   node docs/archive/submit/assets/export-builder-cover.mjs          # article 1 stack
 *   node docs/archive/submit/assets/export-builder-cover.mjs article2 # article 2 trust
 */
import { fileURLToPath, pathToFileURL } from "url";
import path from "path";
import { createRequire } from "module";

const presets = {
  article1: {
    html: "builder-cover.html",
    png: "builder-cover-recoup-stack.png",
    jpeg: null,
  },
  article2: {
    html: "builder-cover-article2.html",
    png: "builder-cover-recoup-trust.png",
    jpeg: "builder-cover-recoup-trust.jpg",
  },
};

const arg = process.argv[2] === "article2" ? "article2" : "article1";
const { html, png, jpeg } = presets[arg];

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../../..");
const require = createRequire(pathToFileURL(path.join(repoRoot, "frontend/package.json")));
const { chromium } = require("playwright");
const htmlPath = path.join(here, html);
const outPath = path.join(here, png);
const fileUrl = `file://${htmlPath}`;

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1200, height: 675 },
  deviceScaleFactor: 1,
});
await page.goto(fileUrl, { waitUntil: "networkidle" });
await page.waitForSelector(".diagram-wrap svg", { timeout: 30_000 });
await page.screenshot({ path: outPath, type: "png" });
if (jpeg) {
  const jpegPath = path.join(here, jpeg);
  await page.screenshot({ path: jpegPath, type: "jpeg", quality: 92 });
  console.log(`Wrote ${jpegPath}`);
}
await browser.close();

console.log(`Wrote ${outPath}`);
