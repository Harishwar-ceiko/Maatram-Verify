// Dev-only: runs the all-match application through the real UI and checks the
// verified state plus a live PDF download. Restore app 1 afterwards with
// scripts/reset_app1.py.
// Usage: node scripts/shoot-happy.mjs
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const APP = 1;

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "ananya@student.example", password: "Student@2026" }),
}).then((response) => response.json());
if (!login.access_token) throw new Error("student login failed");
const token = login.access_token;
const auth = { headers: { Authorization: `Bearer ${token}` } };

const before = await fetch(`${API}/applications/${APP}`, auth).then((response) => response.json());
if (before.status !== "submitted" || before.latest_run) {
  throw new Error(`app ${APP} is not in its pre-run state (${before.status})`);
}
const reference = before.reference;

await mkdir("shots", { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.evaluate((value) => localStorage.setItem("maatram.token", value), token);
await page.goto(`${BASE}/applications/${APP}`, { waitUntil: "networkidle0" });
await page.evaluate(() => document.fonts.ready);
await new Promise((resolve) => setTimeout(resolve, 500));

const startText = await page.evaluate(() => document.body.innerText);
if (!startText.includes("Submitted")) throw new Error("app 1 does not start submitted");
if (!startText.includes("PDF available after the checks finish")) {
  throw new Error("report button should be unavailable before the run");
}
await page.screenshot({ path: "shots/happy-before-1440.png", fullPage: false });

const clicked = await page.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.trim().includes("Run checks"),
  );
  if (button instanceof HTMLButtonElement) button.click();
  return Boolean(button);
});
if (!clicked) throw new Error("run checks button not found");

await page.waitForFunction(
  () => {
    const body = document.body.innerText;
    return body.includes("Verified") && !body.includes("Running checks");
  },
  { timeout: 120000, polling: 500 },
);
await new Promise((resolve) => setTimeout(resolve, 800));

const reportReady = await page.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.trim().includes("Validation report"),
  );
  return button instanceof HTMLButtonElement ? !button.disabled : false;
});
if (!reportReady) throw new Error("report button did not unlock after the run");
await page.screenshot({ path: "shots/happy-verified-1440.png", fullPage: true });

const after = await fetch(`${API}/applications/${APP}`, auth).then((response) => response.json());
if (after.status !== "verified") throw new Error(`application status is ${after.status}`);
if (after.latest_run.status !== "completed") throw new Error("run did not complete");
if (after.latest_run.overall !== "pass") throw new Error(`overall is ${after.latest_run.overall}`);
const summary = after.latest_run.summary;
if (summary.mismatched !== 0 || summary.critical !== 0 || summary.warnings !== 0) {
  throw new Error(`unexpected summary ${JSON.stringify(summary)}`);
}

const report = await fetch(`${API}/applications/${APP}/report.pdf`, auth);
if (report.status !== 200) throw new Error(`report route returned ${report.status}`);
const pdf = Buffer.from(await report.arrayBuffer());
if (pdf.subarray(0, 5).toString() !== "%PDF-") throw new Error("report is not a PDF");

await browser.close();
console.log(`${reference} verified: ${summary.matched} marks matched, report ${pdf.length} bytes`);
