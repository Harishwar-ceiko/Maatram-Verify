// Dev-only layout audit: flags horizontal overflow and clipped elements.
// Usage: node scripts/layout-audit.mjs
import puppeteer from "puppeteer-core";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api";

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "ananya@student.example", password: "Student@2026" }),
}).then((response) => response.json());

const adminLogin = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "admin@maatram.example", password: "Admin@2026" }),
}).then((response) => response.json());

const pages = {
  student: ["/overview", "/applications", "/applications/new", "/applications/2", "/applications/5"],
  admin: [
    "/admin",
    "/admin/applications",
    "/admin/applications/2",
    "/admin/applications/3",
    "/admin/audit",
    "/admin/reviews",
    "/admin/accuracy",
  ],
};

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox"],
});

for (const width of [390, 768, 1024, 1440]) {
  const page = await browser.newPage();
  await page.setViewport({ width, height: 900 });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  for (const [role, paths] of Object.entries(pages)) {
    const token = role === "admin" ? adminLogin.access_token : login.access_token;
    await page.evaluate((value) => localStorage.setItem("maatram.token", value), token);
    for (const path of paths) {
      await page.goto(`${BASE}${path}`, { waitUntil: "networkidle0" });
      await new Promise((resolve) => setTimeout(resolve, 400));
      const report = await page.evaluate(() => {
        const viewport = document.documentElement.clientWidth;
        // html uses overflow-x: clip, so gate on body: the real layout width.
        const overflow = document.body.scrollWidth - viewport;

        function clippedByAncestor(element) {
          let parent = element.parentElement;
          while (parent && parent !== document.body) {
            const style = getComputedStyle(parent);
            if (["auto", "hidden", "scroll", "clip"].includes(style.overflowX)) return true;
            parent = parent.parentElement;
          }
          return false;
        }

        const offenders = [];
        for (const element of document.querySelectorAll("body *")) {
          const rect = element.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) continue;
          if (rect.right > viewport + 1) {
            const style = getComputedStyle(element);
            if (style.position === "fixed" || style.visibility === "hidden") continue;
            if (clippedByAncestor(element)) continue;
            const path = [];
            let node = element;
            while (node && node !== document.body && path.length < 4) {
              path.unshift(
                `${node.tagName.toLowerCase()}${node.className ? "." + String(node.className).split(" ").slice(0, 2).join(".") : ""}`,
              );
              node = node.parentElement;
            }
            offenders.push({
              path: path.join(" > "),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
            });
          }
        }
        return { overflow, offenders: offenders.slice(0, 8) };
      });
      const flag = report.overflow > 1 || report.offenders.length ? "OVERFLOW" : "ok";
      console.log(`${width}px ${path} ${flag}`);
      if (flag !== "ok") {
        console.log(`  scroll overflow ${report.overflow}px`);
        for (const item of report.offenders) {
          console.log(`  right=${item.right} width=${item.width} ${item.path}`);
        }
      }
    }
  }
  await page.close();
}

await browser.close();
