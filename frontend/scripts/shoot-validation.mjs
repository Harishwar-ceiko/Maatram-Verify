// Dev-only: runs the real checks from the UI, then captures the report.
// Usage: node scripts/shoot-validation.mjs
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const APP = "2";

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
await page.setViewport({ width: 1440, height: 1200, deviceScaleFactor: 1 });
await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.evaluate((token) => localStorage.setItem("maatram.token", token), login.access_token);
await page.goto(`${BASE}/applications/${APP}`, { waitUntil: "networkidle0" });
await page.evaluate(() => document.fonts.ready);
await new Promise((resolve) => setTimeout(resolve, 700));

async function buttonWithText(text) {
  return page.evaluate((needle) => {
    const button = [...document.querySelectorAll("button")].find((candidate) =>
      candidate.textContent?.trim().includes(needle),
    );
    if (button instanceof HTMLElement) button.click();
    return Boolean(button);
  }, text);
}

const clicked = await buttonWithText("Re-run checks") || (await buttonWithText("Run checks"));
if (!clicked) throw new Error("run button not found");

// Wait until the run is no longer in flight and a report is on the page.
await new Promise((resolve) => setTimeout(resolve, 900));
await page.waitForFunction(
  () => {
    const body = document.body.innerText;
    const running =
      body.includes("Running checks") || body.includes("Reading the documents at 300 DPI");
    const button = [...document.querySelectorAll("button")].find((candidate) =>
      candidate.textContent?.trim().includes("Re-run checks"),
    );
    return !running && Boolean(button) && body.includes("From sheet");
  },
  { timeout: 90000, polling: 500 },
);
await new Promise((resolve) => setTimeout(resolve, 1200));

await page.screenshot({ path: "shots/validation-report-1440.png", fullPage: true });
console.log("saved shots/validation-report-1440.png");

const mobile = await browser.newPage();
await mobile.setViewport({ width: 390, height: 1000, deviceScaleFactor: 1, isMobile: true });
await mobile.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await mobile.evaluate((token) => localStorage.setItem("maatram.token", token), login.access_token);
await mobile.goto(`${BASE}/applications/${APP}`, { waitUntil: "networkidle0" });
await mobile.evaluate(() => document.fonts.ready);
await new Promise((resolve) => setTimeout(resolve, 900));
await mobile.screenshot({ path: "shots/validation-report-390.png", fullPage: true });
console.log("saved shots/validation-report-390.png");

await browser.close();
