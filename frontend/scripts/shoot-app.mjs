// Dev-only visual check: signs in through the real API, then shoots pages.
// Usage: node scripts/shoot-app.mjs [--mobile]
import puppeteer from "puppeteer-core";
import { mkdir } from "node:fs/promises";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";
const mobile = process.argv.includes("--mobile");

const accounts = {
  student: { email: "ananya@student.example", password: "Student@2026" },
  admin: { email: "admin@maatram.example", password: "Admin@2026" },
};

const pages = [
  { role: "student", path: "/overview", name: "student-overview" },
  { role: "student", path: "/applications", name: "student-applications" },
  { role: "student", path: "/applications/new", name: "student-new" },
  { role: "student", path: "/applications/2", name: "student-detail" },
  { role: "student", path: "/applications/5", name: "student-detail-empty" },
  { role: "admin", path: "/admin", name: "admin-overview" },
  { role: "admin", path: "/admin/applications", name: "admin-applications" },
  { role: "admin", path: "/admin/audit", name: "admin-audit" },
];

async function tokenFor(role) {
  const response = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(accounts[role]),
  });
  if (!response.ok) throw new Error(`login failed for ${role}: ${response.status}`);
  return (await response.json()).access_token;
}

await mkdir("shots", { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1"],
});

const tokens = {
  student: await tokenFor("student"),
  admin: await tokenFor("admin"),
};

for (const entry of pages) {
  const page = await browser.newPage();
  await page.setViewport({ width: mobile ? 390 : 1440, height: mobile ? 844 : 900 });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((token) => localStorage.setItem("maatram.token", token), tokens[entry.role]);
  await page.goto(`${BASE}${entry.path}`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 450));
  const suffix = mobile ? "-390" : "-1440";
  await page.screenshot({ path: `shots/${entry.name}${suffix}.png`, fullPage: true });
  console.log(`saved shots/${entry.name}${suffix}.png`);
  await page.close();
}

await browser.close();
