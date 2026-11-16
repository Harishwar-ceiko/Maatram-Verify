// Dev-only: captures the final demo state. Uses pre-minted tokens so no
// auth.login noise reaches the audit log, and makes no review decisions or
// validation runs. Expects the seeded queue (4 open items).
// Usage: node scripts/shoot-demo.mjs
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const TOKENS = { admin: process.env.ADMIN_TOKEN, student: process.env.STUDENT_TOKEN };

if (!TOKENS.admin || !TOKENS.student) {
  throw new Error("ADMIN_TOKEN and STUDENT_TOKEN must be set");
}

const auth = { headers: { Authorization: `Bearer ${TOKENS.admin}` } };
const queue = await fetch(`${API}/admin/reviews`, auth).then((response) => response.json());
if (queue.counts.open !== 4 || queue.counts.active !== 4) {
  throw new Error(`queue is ${queue.counts.open} open / ${queue.counts.active} active`);
}
const references = new Set(queue.items.map((item) => item.reference));
for (const reference of ["MH26-AZ3GX", "MH26-TDVAY", "MH26-V7THG", "MH26-Y4SFD"]) {
  if (!references.has(reference)) throw new Error(`queue is missing ${reference}`);
}
for (const item of queue.items) {
  if (!item.reasons.length) throw new Error(`${item.reference} has no reasons`);
}

const expected = {
  1: { status: "submitted", overall: null },
  2: { status: "needs_review", overall: "fail" },
  3: { status: "needs_review", overall: "fail" },
  4: { status: "needs_review", overall: "fail" },
  5: { status: "needs_review", overall: "review" },
};
for (const [id, state] of Object.entries(expected)) {
  const application = await fetch(`${API}/applications/${id}`, auth).then((response) =>
    response.json(),
  );
  if (application.status !== state.status) {
    throw new Error(`app ${id} status is ${application.status}, expected ${state.status}`);
  }
  const overall = application.latest_run?.overall ?? null;
  if (overall !== state.overall) {
    throw new Error(`app ${id} overall is ${overall}, expected ${state.overall}`);
  }
}

await mkdir("shots", { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});

async function shoot(role, path, name, width = 1440, height = 1000, mobile = false) {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1, isMobile: mobile });
  await page.evaluateOnNewDocument(
    (token) => localStorage.setItem("maatram.token", token),
    TOKENS[role],
  );
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 500));
  const text = await page.evaluate(() => document.body.innerText);
  await page.screenshot({ path: `shots/${name}.png`, fullPage: true });
  await page.close();
  console.log(`saved shots/${name}.png`);
  return text;
}

function requireText(text, needles, label) {
  for (const needle of needles) {
    if (!text.includes(needle)) throw new Error(`${label} is missing "${needle}"`);
  }
}

const queueText = await shoot("admin", "/admin/reviews", "reviews-queue-1440");
requireText(
  queueText,
  ["Review queue", "MH26-AZ3GX", "MH26-TDVAY", "MH26-V7THG", "MH26-Y4SFD", "3 mismatched"],
  "queue",
);

await shoot("admin", "/admin/reviews", "reviews-queue-390", 390, 900, true);

const mismatchText = await shoot(
  "admin",
  "/admin/applications/2",
  "review-detail-1440",
);
requireText(
  mismatchText,
  [
    "Review decision",
    "Why the checker routed it",
    "Mathematics",
    "Entered 85",
    "Physics",
    "Entered 78",
    "Chemistry",
    "Entered 81",
    "Approve record",
    "Reject",
  ],
  "mismatch detail",
);

const photoText = await shoot("admin", "/admin/applications/3", "admin-app3-photo-1440");
requireText(photoText, ["Review decision", "Brightness", "too dark"], "photo detail");

const missingText = await shoot("admin", "/admin/applications/4", "admin-app4-missing-1440");
requireText(
  missingText,
  ["Review decision", "Physics", "missing from the mark sheet"],
  "missing-subject detail",
);

const duplicateText = await shoot(
  "admin",
  "/admin/applications/5",
  "admin-app5-duplicate-1440",
);
requireText(
  duplicateText,
  ["Review decision", "Duplicate upload", "document #2"],
  "duplicate detail",
);

const auditText = await shoot("admin", "/admin/audit", "admin-audit-1440");
requireText(
  auditText,
  [
    "validation.completed",
    "validation.started",
    "validation_run #1",
    "validation_run #5",
    "photo_failures: 1",
  ],
  "audit log",
);
await shoot("admin", "/admin/audit", "admin-audit-390", 390, 900, true);

await shoot("admin", "/admin", "admin-overview-1440");
await shoot("admin", "/admin", "admin-overview-390", 390, 900, true);
await shoot("admin", "/admin/applications", "admin-applications-1440");
await shoot("admin", "/admin/applications", "admin-applications-390", 390, 900, true);

const studentOverview = await shoot("student", "/overview", "student-overview-1440");
requireText(
  studentOverview,
  ["MH26-5PCPR", "MH26-AZ3GX", "MH26-Y4SFD"],
  "student overview",
);
await shoot("student", "/overview", "student-overview-390", 390, 900, true);
await shoot("student", "/applications", "student-applications-1440");
await shoot("student", "/applications", "student-applications-390", 390, 900, true);

const allMatchText = await shoot(
  "student",
  "/applications/1",
  "student-detail-allmatch-1440",
);
requireText(
  allMatchText,
  ["Submitted", "Run checks", "PDF available after the checks finish"],
  "all-match application",
);

const studentMismatchText = await shoot(
  "student",
  "/applications/2",
  "student-detail-1440",
);
requireText(
  studentMismatchText,
  ["Needs review", "Validation report", "Mathematics"],
  "student mismatch detail",
);
await shoot("student", "/applications/2", "student-detail-390", 390, 900, true);

const duplicateStudentText = await shoot(
  "student",
  "/applications/5",
  "student-detail-duplicate-1440",
);
requireText(
  duplicateStudentText,
  ["Needs review", "Duplicate upload", "Validation report"],
  "student duplicate detail",
);

await browser.close();
console.log("demo state captured; queue remains 4 open, app 1 still submitted");
