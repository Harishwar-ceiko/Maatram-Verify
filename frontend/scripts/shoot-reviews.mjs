// Dev-only: verifies the review queue and a real approve decision in the browser.
// Usage: node scripts/shoot-reviews.mjs
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const APP = 3;
const NOTE = "Photograph checked against the register; identity confirmed.";

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "admin@maatram.example", password: "Admin@2026" }),
}).then((response) => response.json());
if (!login.access_token) throw new Error("admin login failed");
const token = login.access_token;
const auth = { headers: { Authorization: `Bearer ${token}` } };

const before = await fetch(`${API}/applications/${APP}`, auth).then((response) => response.json());
const reference = before.reference;
if (!before.review || before.review.status !== "open") {
  throw new Error(`app ${APP} (${reference}) is not waiting for review`);
}

await mkdir("shots", { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});

async function open(path, width = 1440, height = 1000, mobile = false) {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1, isMobile: mobile });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((value) => localStorage.setItem("maatram.token", value), token);
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 500));
  return page;
}

function bodyText(page) {
  return page.evaluate(() => document.body.innerText);
}

// Queue at desktop and mobile before deciding anything.
const queue = await open("/admin/reviews");
const queueText = await bodyText(queue);
for (const needle of ["Review queue", "Awaiting first look", reference, "To review", "3 mismatched"]) {
  if (!queueText.includes(needle)) throw new Error(`queue is missing ${needle}`);
}
await queue.screenshot({ path: "shots/reviews-queue-1440.png", fullPage: true });
console.log("queue shows the open mismatch item");

const queueMobile = await open("/admin/reviews", 390, 900, true);
await queueMobile.screenshot({ path: "shots/reviews-queue-390.png", fullPage: true });
console.log("mobile queue captured");

// Open the bad-photo item and inspect the decision panel.
const detail = await open(`/admin/applications/${APP}`);
const detailText = await bodyText(detail);
for (const needle of ["Review decision", "Why the checker routed it", "Decision note", "Approve record"]) {
  if (!detailText.includes(needle)) throw new Error(`detail is missing ${needle}`);
}
if (!detailText.includes("too dark")) throw new Error("the photo reason is not shown");
await detail.screenshot({ path: "shots/review-detail-1440.png", fullPage: true });

const detailMobile = await open(`/admin/applications/${APP}`, 390, 900, true);
await detailMobile.screenshot({ path: "shots/review-detail-390.png", fullPage: true });
console.log("decision panel rendered at 1440 and 390");

await detail.bringToFront();

const approveState = await detail.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.includes("Approve record"),
  );
  if (!(button instanceof HTMLButtonElement)) throw new Error("approve button not found");
  return { disabled: button.disabled };
});
if (!approveState.disabled) {
  throw new Error("approve should be disabled until a note is written");
}
await detail.type("#review-comment", NOTE);
const readyState = await detail.evaluate(() => {
  const button = [...document.querySelectorAll("button")].find((candidate) =>
    candidate.textContent?.includes("Approve record"),
  );
  if (!(button instanceof HTMLButtonElement)) throw new Error("approve button not found");
  return { disabled: button.disabled };
});
if (readyState.disabled) {
  throw new Error("approve stayed disabled after typing a note");
}

await Promise.all([
  detail.waitForFunction(
    () => document.body.innerText.includes("Recorded decision"),
    { timeout: 15000, polling: 100 },
  ),
  detail.evaluate(() => {
    const button = [...document.querySelectorAll("button")].find((candidate) =>
      candidate.textContent?.includes("Approve record"),
    );
    if (button instanceof HTMLButtonElement) button.click();
  }),
]);
const decidedText = await bodyText(detail);
if (!decidedText.includes(NOTE)) throw new Error("the decision note is not shown");
await detail.screenshot({ path: "shots/review-decided-1440.png", fullPage: false });
console.log("approve decision recorded in the UI");

// The API must agree, and the queue counts must move.
const after = await fetch(`${API}/applications/${APP}`, auth).then((response) => response.json());
if (after.status !== "approved") throw new Error(`application status is ${after.status}`);
if (after.review.status !== "approved") throw new Error(`review status is ${after.review.status}`);
if (after.review.decision_comment !== NOTE) throw new Error("stored note differs");
const queueAfter = await fetch(`${API}/admin/reviews`, auth).then((response) => response.json());
if (queueAfter.counts.active !== 3) throw new Error(`active count is ${queueAfter.counts.active}`);
if (queueAfter.counts.approved !== 1) throw new Error(`approved count is ${queueAfter.counts.approved}`);

const audit = await open("/admin/audit");
const auditText = await bodyText(audit);
if (!auditText.includes("review.approved")) throw new Error("audit entry is missing");
if (!auditText.includes(reference)) throw new Error("audit entry lost the application reference");
await audit.screenshot({ path: "shots/review-audit-1440.png", fullPage: true });
console.log("audit log carries review.approved with the reference");

await browser.close();
console.log(`approved ${reference}; queue is now ${queueAfter.counts.active} active / ${queueAfter.counts.approved} approved`);
