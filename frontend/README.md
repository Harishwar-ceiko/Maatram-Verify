# Maatram Verify — frontend

React 19 + TypeScript + Vite + Tailwind CSS 4. The product is described in the
[root README](../README.md); the three-minute walkthrough is in
[`DEMO.md`](../DEMO.md).

## Development

```powershell
npm install
npm run dev
```

The app expects the API at `http://127.0.0.1:8000`. Vite proxies `/api` so the
browser can use same-origin paths. Set `VITE_API_URL` (backend origin, no `/api`)
to call a deployed API instead; leave it blank locally to keep using the proxy.

```powershell
npm run build     # tsc -b + production build
npm run lint      # oxlint
npm run preview   # serve the production build
```

## Structure

```text
src/
  pages/          student and admin routes
  components/     validation, documents, review, shared UI
  lib/            API client, auth context, query client, labels
  styles/         design tokens and component styles
```

The visual system is warm paper and ink with vermilion for action, pass green,
fail red and amber for review. Newsreader carries headings, IBM Plex Sans the
interface, IBM Plex Mono references and timestamps. Status is never encoded by
colour alone: square markers and text labels travel together.

## Dev-only browser checks

These scripts use `puppeteer-core` and a local Chrome install. They are not part
of the app build.

| Script | Purpose |
| --- | --- |
| `scripts/layout-audit.mjs` | Overflow/clipping check across 12 pages at 390/768/1024/1440 |
| `scripts/shoot-demo.mjs` | Final demo-state screenshots without touching the queue |
| `scripts/shoot-happy.mjs` | Runs app 1 live and verifies the report unlocks |
| `scripts/shoot-reviews.mjs` | Approves a queue item and checks the audit log |
| `scripts/shoot-report.mjs` | Downloads and verifies the PDF |

Screenshots land in `shots/`, which is gitignored. After using the demo scripts,
run `backend/scripts/reset_demo.py` to restore the seeded queue.
