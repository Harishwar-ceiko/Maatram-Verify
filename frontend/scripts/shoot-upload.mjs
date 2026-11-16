// Dev-only: exercises the real upload UI end to end, then shoots the result.
// Usage: node scripts/shoot-upload.mjs
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const SHEET = "C:/Users/Vinoth/Desktop/hack/backend/samples/marksheet-reg2026a014.png";
const PHOTO = "C:/Users/Vinoth/Desktop/hack/backend/samples/photo-ananya.png";
const APP = 2;

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "ananya@student.example", password: "Student@2026" }),
}).then((response) => response.json());

if (!login.access_token) throw new Error("login failed");

await mkdir("shots", { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});

const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1100 });
await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.evaluate((token) => localStorage.setItem("maatram.token", token), login.access_token);
await page.goto(`${BASE}/applications/${APP}`, { waitUntil: "networkidle0" });
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: "shots/upload-empty-1440.png", fullPage: true });
console.log("saved shots/upload-empty-1440.png");

async function upload(selectorIndex, path) {
  const inputs = await page.$$('input[type="file"]');
  await inputs[selectorIndex].uploadFile(path);
}

async function present(name) {
  return page.evaluate((needle) => document.body.innerText.includes(needle), name);
}

if (!(await present("marksheet-reg2026a014.png"))) {
  await upload(0, SHEET);
  await page.waitForFunction(
    (name) => document.body.innerText.includes(name),
    { timeout: 30000 },
    "marksheet-reg2026a014.png",
  );
  await new Promise((resolve) => setTimeout(resolve, 800));
}

if (!(await present("photo-ananya.png"))) {
  await upload(1, PHOTO);
  await page.waitForFunction(
    (name) => document.body.innerText.includes(name),
    { timeout: 30000 },
    "photo-ananya.png",
  );
  await new Promise((resolve) => setTimeout(resolve, 1200));
}

await new Promise((resolve) => setTimeout(resolve, 1500));
await page.screenshot({ path: "shots/upload-filled-1440.png", fullPage: true });
console.log("saved shots/upload-filled-1440.png");

// Open the first mark sheet in the viewer. Clicking through the DOM avoids a
// stale element handle if a background query refresh replaces the row.
await page.evaluate(() => {
  const button = [...document.querySelectorAll("button[aria-label]")].find((candidate) =>
    candidate.getAttribute("aria-label")?.startsWith("Open marksheet"),
  );
  if (button instanceof HTMLElement) button.click();
});
await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
await new Promise((resolve) => setTimeout(resolve, 1200));
await page.screenshot({ path: "shots/upload-viewer-1440.png" });
console.log("saved shots/upload-viewer-1440.png");

await browser.close();
