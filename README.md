# Maatram Verify

**Deterministic admission document validation for Maatram Foundation.**
Built for Maatram HackForge 2026-27, Problem Statement **MH26-01: Smart Admission Document Validation**.

Maatram Verify cross-checks the documents a student uploads against the values they typed into the admission form, flags every discrepancy at field level, validates the profile photograph against measurable quality rules, and routes doubtful cases to a human reviewer. The core validation pipeline uses **no Generative AI or LLMs**. It relies only on OCR, classical image processing and rule engines, so every result is explainable and auditable.

> All documents, names and numbers in this repository are **synthetic**. No real student documents or real Aadhaar numbers are used anywhere.

---

## Table of contents

1. [Background](#background)
2. [What it does](#what-it-does)
3. [How it works](#how-it-works)
4. [Tech stack](#tech-stack)
5. [Project structure](#project-structure)
6. [Getting started](#getting-started)
7. [Demo accounts and data](#demo-accounts-and-data)
8. [Testing and accuracy](#testing-and-accuracy)
9. [Security and privacy](#security-and-privacy)
10. [Configuration](#configuration)
11. [Deployment](#deployment)
12. [Scope and roadmap](#scope-and-roadmap)
13. [Team](#team)

---

## Background

Maatram Foundation offers free college seats to deserving students, including students from low-income families, orphans and first-generation graduates. Applicants go through several checks: document verification, call verification and physical verification of their circumstances. After that, they receive college choices based on their marks.

The first stage, document verification, is slow and error-prone when done by hand. Marks are mistyped, mark sheets are incomplete, photographs are unusable, and details differ between documents. **Maatram Verify automates this first stage.** The call and physical verification stages and seat allocation are outside the scope of this project.

## What it does

| Area | Capability |
|---|---|
| **Accounts** | Student registration and login, admin role, role-based access control |
| **Applications** | Applicant details plus entered marks for Class 10, Class 11 (optional) and Class 12 |
| **Document upload** | PDF, JPG and PNG, multiple documents, verified by file signature, not just extension |
| **Document types** | Class 10, 11 and 12 mark sheets, Aadhaar, income certificate, community certificate, first graduate certificate, profile photograph |
| **OCR extraction** | Subject names, marks, register numbers, names and dates, each with a confidence score |
| **Mark verification** | Subject-wise Match, Mismatch, Missing-in-upload and Missing-in-entry, with the difference stored |
| **Aadhaar checks** | 12-digit format, Verhoeff checksum, QR code decode compared with printed text, masked display |
| **Income certificate** | Income against a configurable limit, issue date against a configurable validity window |
| **Photo validation** | Resolution, height and width, aspect ratio, file size, format, orientation, brightness, blur and pixel checks |
| **Consistency checks** | Name, date of birth, parent names and address compared across all documents, and across Classes 10, 11 and 12 |
| **Missing data** | Missing subjects, incomplete fields, exact duplicates and near-duplicate documents |
| **Live dashboard** | Match, Mismatch, Pass, Fail and Pending statuses that update as validation runs |
| **PDF report** | Downloadable report per application with entered vs uploaded values and discrepancies highlighted |
| **Admin review** | Exception queue, side-by-side document view, value correction, approve or reject with a mandatory comment, full audit log |
| **Accuracy testing** | Synthetic data generator, evaluation script and an Accuracy page |

### Example report

The report follows the format given in the problem statement:

| Validation | Result | Details |
|---|---|---|
| Mathematics Marks | Mismatch | Entered: 85, Uploaded: 88 |
| English Marks | Match | Entered: 92, Uploaded: 92 |
| Mark Sheet Completeness | Pass | All required subjects present |
| Photo Resolution | Fail | 180 x 220; minimum: 300 x 400 |
| Photo Aspect Ratio | Pass | Within accepted range |
| File Format | Pass | JPEG |

## How it works

```
Student                        Backend pipeline                              Admin
-------                        ----------------                              -----
Fill form  ──►  Upload docs ──►  1. Validate file (signature, size)
                                 2. Classify document type (keyword rules)
                                 3. Preprocess image (grayscale, denoise,
                                    threshold, deskew)
                                 4. OCR (Tesseract) + table parsing
                                 5. Extract fields + confidence
                                 6. Compare entered vs uploaded
                                 7. Validate photo, Aadhaar, income, etc.
                                 8. Cross-document consistency matrix
                                 9. Verdict + PDF report
                                          │
                       clean ◄────────────┴────────────► flagged / low confidence
                     verified                                      │
                                                                   ▼
                                                      Exception queue ──► review,
                                                                          correct,
                                                                          approve / reject
                                                                          (audit logged)
```

Design principles:

- **Deterministic and explainable.** Every verdict traces back to a rule, a threshold or a measured value.
- **Human in the loop.** Anything doubtful goes to a reviewer rather than being silently passed or failed.
- **Configurable.** All thresholds, required subjects, alias maps and rules live in a single configuration file.
- **Testable.** Validators are small pure functions with unit tests.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, SQLite, Pydantic |
| OCR | Tesseract (pytesseract), optional PaddleOCR behind a swappable interface |
| Image processing | OpenCV, Pillow, NumPy, PyMuPDF (PDF to image) |
| Matching | rapidfuzz (fuzzy subject and name matching) |
| Reports | ReportLab |
| Security | bcrypt (passlib), JWT (python-jose), Fernet encryption (cryptography) |
| Frontend | React, Vite, TypeScript, Tailwind CSS, TanStack Query, Recharts |
| Testing | pytest |

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # HTTP routes
│   │   ├── services/       # Application logic, orchestration
│   │   ├── ocr/            # OCR engine interface, preprocessing, table parsing
│   │   ├── validators/     # Pure validation functions
│   │   ├── models/         # Database models
│   │   ├── reports/        # PDF report generation
│   │   └── main.py
│   ├── scripts/
│   │   ├── seed.py         # Creates demo users and sample applications
│   │   └── reset_demo.py   # Restores the demo state after a rehearsal
│   ├── tests/              # pytest suite
│   └── requirements.txt
├── frontend/               # React + Vite application
├── docs/                   # Screenshots and supporting material
├── DEMO.md                 # Three-minute demo walkthrough
└── README.md
```

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer
- **Tesseract OCR** installed and available on your `PATH`
  - Windows: install from the [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki)
  - Ubuntu / Kali: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Verify with `tesseract --version`

### 1. Clone

```bash
git clone https://github.com/robinxheart/Maatram-Verify.git
cd Maatram-Verify
```

### 2. Backend

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Linux / macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Edit `.env` and set your own `SECRET_KEY` and `FERNET_KEY`. Generate them with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The API documentation is then available at http://127.0.0.1:8000/docs.

### 3. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

### Troubleshooting

| Problem | Fix |
|---|---|
| `Errno 10048` / address already in use | Another process is on port 8000. Stop it, or start uvicorn on a different port and update the frontend API URL |
| `tesseract is not installed` | Install Tesseract and make sure `tesseract --version` works, or set `TESSERACT_CMD` in `.env` |
| PowerShell blocks activation | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Frontend cannot reach the API | Confirm the backend is running on port 8000 |

## Demo accounts and data

`scripts/seed.py` creates one administrator, a student account and ten sample applications. Each application covers one scenario:

| # | Scenario |
|---|---|
| 1 | Submitted, no validation run yet (used for the live demo) |
| 2 | Marks mismatch |
| 3 | Bad profile photo |
| 4 | Missing subject |
| 5 | Duplicate upload |
| 6 | Income above limit |
| 7 | Expired income certificate |
| 8 | Aadhaar checksum failure |
| 9 | Community certificate name conflict |
| 10 | Class 11 and Class 12 name conflict |

> The accounts below are **demo credentials for synthetic data only**. Change them before exposing the app publicly.

| Role | Email | Password |
|---|---|---|
| Admin | `admin@maatram.example` | `Admin@2026` |
| Student | `ananya@student.example` | `Student@2026` |

After any rehearsal, restore the demo state:

```bash
cd backend
python scripts/reset_demo.py
```

A timed three-minute walkthrough is in [DEMO.md](DEMO.md).

## Testing and accuracy

### Unit and integration tests

```bash
cd backend
python -m pytest
```

The suite currently has **140 tests** covering the validators, comparison logic, cross-document checks and the seeded scenarios.

### Accuracy evaluation

The evaluation script runs the full pipeline over a synthetic corpus and reports field-level extraction accuracy, mismatch detection precision and recall, photo validation accuracy and a confusion matrix. Results are saved as a markdown report and shown on the admin **Accuracy** page.

| Corpus | Size | Result |
|---|---|---|
| `synthetic-v2` | 30 mark sheets | 100% on headline metrics, 42 of 42 documents classified correctly |

**Please note:** the synthetic corpus is generated by this project's own templates, with varied layouts, fonts and noise (blur, rotation, low contrast). Real-world scans will be messier. This is why low-confidence extractions are routed to the review queue instead of being trusted automatically.

To regenerate data and re-run the evaluation, see the scripts in `backend/scripts/` (documented in `docs/`).

## Security and privacy

- **Passwords** hashed with bcrypt; **JWT** access tokens
- **Role-based access control** enforced on the backend and the frontend. Students can see only their own applications; administrators can see all
- **Encryption at rest.** Uploaded files and Aadhaar numbers are encrypted with Fernet
- **Aadhaar masking.** Only the last four digits are shown in the interface, logs, audit entries and reports
- **Authenticated file access.** Documents are served only through endpoints that check ownership
- **Upload hardening.** Signature (magic byte) checks, size limits and filename sanitisation
- **Rate limiting** on login
- **Audit log.** Who did what and when, for every review action
- **No secrets in the repository.** Configuration comes from environment variables; see `.env.example`

## Configuration

All business rules are in one configuration file, so they can be adjusted without touching code:

- Photo rules: minimum and maximum dimensions, aspect ratio range, file size range, formats, brightness range, blur threshold
- Required subjects and subject alias maps, per class
- Fuzzy matching thresholds
- Income limit and certificate validity window
- Confidence threshold below which a field goes to manual review

Environment variables (see `.env.example`): `SECRET_KEY`, `FERNET_KEY`, `DATABASE_URL`, `STORAGE_DIR`, `CORS_ORIGINS`, `TESSERACT_CMD`.

## Deployment

The frontend can be hosted on a static platform such as Vercel. The backend needs Tesseract, persistent storage and background tasks, so it should run in a container (for example on Render, Railway or Fly.io). See `DEPLOY.md` if present for step-by-step instructions.

## Scope and roadmap

**In scope:** document verification, covering mark sheets (Class 10, 11, 12), profile photograph, Aadhaar, income, community and first graduate certificates, plus the admin exception queue.

**Out of scope for this prototype:**

- Call verification and physical verification workflow
- College choices and seat allocation
- Integration with government verification services

**Possible next steps:** call and physical verification tracking, SMS or email notifications, support for regional-language mark sheets, a production database (PostgreSQL) and object storage, and evaluation on a larger set of anonymised real-world scans with appropriate consent.

## Team

Built by **Hackforge26** for Maatram HackForge 2026-27.

| Name | Role |
|---|---|
| Vinoth Paulraj | Prototype lead, full-stack development |

---

*Built for the Maatram Community track. Not an official Maatram Foundation product.*
