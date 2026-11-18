# Deploying Maatram Verify

Two services:

| Piece | Platform | Runtime |
|---|---|---|
| API, OCR pipeline, SQLite, encrypted uploads | Render | Docker (`backend/Dockerfile`) |
| React single-page app | Vercel | Static Vite build (`frontend/`) |

The validation pipeline is unchanged by deployment. It still runs only Tesseract,
OpenCV/Pillow, PyMuPDF, regex, rapidfuzz and the rule engines — no generative AI.
All demo documents and numbers are synthetic.

> **Single instance only.** SQLite and encrypted uploads both live on one Render
> disk. Do not scale the API to multiple instances or deploy it to an ephemeral
> filesystem, or uploads and data will be split or lost.

---

## 1. Generate the two secrets

Run these locally once and keep the values. Reusing the same `FERNET_KEY` matters:
changing it makes previously stored documents unreadable.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first output is `SECRET_KEY`; the second is `FERNET_KEY`.

---

## 2. Backend on Render (Docker)

1. Push this repository to GitHub/GitLab.
2. In Render, choose **New → Web Service** and connect the repository.
3. Configure the service:
   - **Name:** `maatram-verify-api` (or any name)
   - **Region:** closest to the demo audience
   - **Root Directory:** `backend`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `./Dockerfile`
   - **Instance Type:** `Starter` or larger. Persistent disks are not available on
     free instance types; without a disk the database and uploads reset on every
     deploy.
   - **Health Check Path:** `/health`
4. Add a persistent disk under **Advanced → Disks**:
   - **Name:** `maatram-data`
   - **Mount Path:** `/var/data`
   - **Size:** `1 GB` is enough for the prototype
5. Add these environment variables under **Environment**:

| Variable | Required | Value |
|---|---|---|
| `APP_ENV` | yes | `production` |
| `SECRET_KEY` | yes | output 1 from step 1 |
| `FERNET_KEY` | yes | output 2 from step 1 |
| `DATABASE_URL` | yes | `sqlite:////var/data/admissions.db` |
| `STORAGE_DIR` | yes | `/var/data/uploads` |
| `CORS_ORIGINS` | yes | `https://your-app.vercel.app` |
| `SEED_ON_START` | recommended | `true` on the first deploy |

Notes:

- `DATABASE_URL` has **four** slashes: `sqlite:///` plus the absolute path
  `/var/data/admissions.db`.
- `CORS_ORIGINS` is comma-separated and must contain only the frontend origins
  that should receive CORS headers, for example
  `https://maatram-verify.vercel.app,https://maatram-verify-git-main.vercel.app`.
  No trailing slash. A browser request from any other origin is rejected.
- `PORT` is provided by Render automatically. The Dockerfile defaults it to
  `8000` when it is unset.
- `SEED_ON_START=true` is safe to leave on: it seeds only when the database has
  **neither users nor applications**. A database with existing work is never
  touched. Set it to `false` afterwards if you prefer explicit control.
- Leave `TESSERACT_CMD` unset in the image — Tesseract is installed and on
  `PATH`. It exists for local Windows installs.
- Optional tuning variables: `ACCESS_TOKEN_EXPIRE_MINUTES` (default `120`),
  `MAX_UPLOAD_MB` (`15`), `OCR_ENGINE` (`tesseract`), `LOGIN_RATE_LIMIT` (`8`),
  `LOGIN_RATE_WINDOW_SECONDS` (`300`). The full list with comments is in
  [`backend/.env.example`](backend/.env.example).

6. Click **Create Web Service** and wait for the Docker build. The first boot
   with `SEED_ON_START=true` generates the synthetic documents and runs the demo
   validations, so it can take a few minutes; later boots skip seeding.
7. Verify:
   - `https://your-api.onrender.com/health` returns `"service": "ok"` and the
     Tesseract status. `/api/health` remains available as an alias.
   - The API docs load at `https://your-api.onrender.com/docs`.
8. Copy the backend URL — you need it for Vercel in the next step.

---

## 3. Frontend on Vercel

1. In Vercel, choose **Add New → Project** and import the same repository.
2. Configure the project:
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Add an environment variable for **Production** (and **Preview** if preview
   deployments must work):

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://your-api.onrender.com` |

Use the backend **origin only**: no `/api` path, no trailing slash. The client
appends `/api` itself. `VITE_API_URL` is baked in at build time, so changing it
requires a redeploy.

4. Click **Deploy**.
5. Copy the Vercel production URL, go back to Render, set `CORS_ORIGINS` to that
   exact origin, and save. Render restarts the service with the new value.
6. Open the Vercel URL, log in with a demo account, and refresh a deep link such
   as `/applications/1`. The rewrite in
   [`frontend/vercel.json`](frontend/vercel.json) serves `index.html` so the
   route survives a refresh.

If you use Vercel preview deployments, either add each preview origin to
`CORS_ORIGINS` (comma-separated) or test against the production URL.

---

## 4. Local Docker check (optional)

Build the same image Render uses:

```bash
cd backend
docker build -t maatram-verify-api .
```

Run it with a named volume standing in for the Render disk:

```bash
docker run --rm -p 8000:8000 \
  -e APP_ENV=production \
  -e SECRET_KEY="<output 1>" \
  -e FERNET_KEY="<output 2>" \
  -e DATABASE_URL="sqlite:////data/admissions.db" \
  -e STORAGE_DIR="/data/uploads" \
  -e CORS_ORIGINS="http://localhost:5173" \
  -e SEED_ON_START=true \
  -v maatram-data:/data \
  maatram-verify-api
```

Then run the frontend with `npm run dev` from `frontend/` and leave
`VITE_API_URL` blank: the Vite proxy forwards `/api` to
`http://127.0.0.1:8000`.

---

## 5. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Browser says `Cannot reach the server` | `VITE_API_URL` missing or wrong on Vercel, or the Render service is asleep/failed. Recheck the URL and redeploy the frontend after changing it. |
| CORS error in the browser console | `CORS_ORIGINS` does not exactly match the frontend origin (scheme, host, port, no trailing slash). Update it and restart Render. |
| 500 on first boot with missing settings | `APP_ENV=production` requires both `SECRET_KEY` and `FERNET_KEY`. Add them and redeploy. |
| Demo data missing after deploy | `SEED_ON_START` is false, or the database already contains users/applications (seed is intentionally skipped). Check the Render logs. |
| Uploads or applications disappear after redeploy | No persistent disk attached, or the disk is mounted somewhere other than `/var/data`. Recheck the mount path and `DATABASE_URL` / `STORAGE_DIR`. |
| `/health` shows Tesseract unavailable | The container was not built from `backend/Dockerfile`, or the build failed during the `apt-get` step. Rebuild and check logs. |
