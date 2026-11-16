// Dev-only: clicks the report download in the real UI and checks the PDF lands.
// Usage: node scripts/shoot-report.mjs
import puppeteer from "puppeteer-core";
import { mkdir, readdir, readFile, rm } from "node:fs/promises";
import path from "node:path";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const APP = "2";

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "ananya@student.example", password: "Student@2026" }),
}).then((response) => response.json());
if (!login.access_token) throw new Error("student login failed");

await mkdir("shots", { recursive: true });
const downloads = path.resolve("shots/downloads");
await rm(downloads, { recursive: true, force: true });
await mkdir(downloads, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});

async function open(width, height, mobile = false) {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1, isMobile: mobile });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((token) => localStorage.setItem("maatram.token", token), login.access_token);
  await page.goto(`${BASE}/applications/${APP}`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 700));
  return page;
}

const page = await open(1440, 1000);

const buttonState = await page.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.trim().includes("Validation report"),
  );
  return button instanceof HTMLButtonElement
    ? { found: true, disabled: button.disabled }
    : { found: false, disabled: null };
});
if (!buttonState.found) throw new Error("report button not found");
if (buttonState.disabled) throw new Error("report button is disabled for a completed run");

await page.screenshot({ path: "shots/report-button-1440.png", fullPage: false });

const client = await page.createCDPSession();
await client.send("Browser.setDownloadBehavior", {
  behavior: "allow",
  downloadPath: downloads,
  eventsEnabled: true,
});

await page.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.trim().includes("Validation report"),
  );
  if (button instanceof HTMLButtonElement) button.click();
});

let file = null;
const deadline = Date.now() + 30000;
while (Date.now() < deadline) {
  const names = await readdir(downloads);
  const pdf = names.find((name) => name.endsWith(".pdf"));
  if (pdf) {
    file = path.join(downloads, pdf);
    break;
  }
  await new Promise((resolve) => setTimeout(resolve, 250));
}
if (!file) throw new Error("the PDF never landed in the download folder");

const data = await readFile(file);
if (data.subarray(0, 5).toString() !== "%PDF-") throw new Error("downloaded file is not a PDF");
console.log(`downloaded ${path.basename(file)} (${data.length} bytes)`);

const mobile = await open(390, 1000, true);
await mobile.screenshot({ path: "shots/report-button-390.png", fullPage: false });

await browser.close();
