// Dev-only: opens the admin accuracy page and captures the evaluated state.
// Usage: node scripts/shoot-accuracy.mjs [--run]
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const RUN = process.argv.includes("--run");

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "admin@maatram.example", password: "Admin@2026" }),
}).then((response) => response.json());
if (!login.access_token) throw new Error("admin login failed");

await mkdir("shots", { recursive: true });
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
  await page.goto(`${BASE}/admin/accuracy`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 700));
  return page;
}

const page = await open(1440, 1100);

if (RUN) {
  const clicked = await page.evaluate(() => {
    const button = [...document.querySelectorAll("button")].find((candidate) =>
      candidate.textContent?.trim().includes("Run again") ||
      candidate.textContent?.trim().includes("Run evaluation"),
    );
    if (button instanceof HTMLElement) button.click();
    return Boolean(button);
  });
  if (!clicked) throw new Error("run button not found");
  await new Promise((resolve) => setTimeout(resolve, 900));
  await page.screenshot({ path: "shots/accuracy-running-1440.png", fullPage: true });
  console.log("saved shots/accuracy-running-1440.png");

  await page.waitForFunction(
    () => {
      const body = document.body.innerText;
      return (
        !body.includes("Running evaluation") &&
        !body.includes("Reading the synthetic set") &&
        body.includes("Mismatch recall") &&
        body.includes("Mark verification")
      );
    },
    { timeout: 180000, polling: 1000 },
  );
  await new Promise((resolve) => setTimeout(resolve, 1000));
}

await page.screenshot({ path: "shots/accuracy-1440.png", fullPage: true });
console.log("saved shots/accuracy-1440.png");

const mobile = await open(390, 1000, true);
await mobile.screenshot({ path: "shots/accuracy-390.png", fullPage: true });
console.log("saved shots/accuracy-390.png");

await browser.close();
