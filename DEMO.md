# Maatram Verify — three-minute demo

**Problem MH26-01 · Smart Admission Document Validation**

Applicants enter Classes 10, 11 and 12, attach mark sheets, a portrait and
supporting certificates, and the checker reads every file. It compares each
subject, measures the portrait, checks identity across documents, applies the
income, community and first-graduate rules, detects duplicates, and sends only
the exceptions to a person. Every decision comes from Tesseract,
OpenCV/Pillow, regex, rapidfuzz and fixed rules. **No generative model touches
a decision.**

---

## Before the demo (two minutes)

### Services

```powershell
# Terminal 1
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2
cd frontend
npm run dev
```

Open the browser at `http://127.0.0.1:5173`.

### Two windows, two roles

| Window | Role | Sign in as |
| --- | --- | --- |
| A — normal Chrome | Admissions office | `admin@maatram.example` / `Admin@2026` |
| B — incognito | Applicant | `ananya@student.example` / `Student@2026` |

Keep Window A on **Admissions overview** and Window B on **Your applications**.
Use 100% zoom, hide bookmarks, and close DevTools. Leave a PDF viewer ready.

### Seeded state

The current database is already seeded. It holds **10 applications**, **9 open
review items** and one completed `synthetic-v2` accuracy run. The queue order
is priority first, then arrival: eight critical items (priority 20) followed by
one standard warning (priority 50).

| Student | Scenario | Reference | State |
| --- | --- | --- | --- |
| Ananya | All valid — live run | `MH26-22LXR` | Submitted — no run yet |
| Ananya | Mark mismatch | `MH26-9JPYD` | Needs review — 3 mark mismatches |
| Rohan | Bad photograph | `MH26-BCHTZ` | Needs review — brightness 27/255 |
| Rohan | Missing subject | `MH26-KUCYC` | Needs review — Physics missing |
| Ananya | Duplicate upload | `MH26-H4YD6` | Needs review — duplicate warning |
| Ananya | Income above the limit | `MH26-AEB4R` | Needs review — INR 320,000 |
| Rohan | Expired income certificate | `MH26-9REHG` | Needs review — expired 2026-07-06 |
| Ananya | Aadhaar checksum failure | `MH26-X9PTD` | Needs review — Verhoeff failure |
| Rohan | Community name conflict | `MH26-FNARB` | Needs review — Arjun vs Rohan |
| Ananya | Class 11 vs Class 12 name | `MH26-9MMS3` | Needs review — Ananya Ramanathan |

If the demo has been run before, restore this state without changing the
references:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\reset_demo.py
```

Do **not** run `seed.py --reset` immediately before a demo: it generates new
references and clears the accuracy run. If you seed a fresh clone, run
`python scripts\seed.py --reset`, then `python scripts\evaluate.py`, and use the
references printed by the seed. The reset script above keeps the references
stable.

---

## Run of show

### 0:00–0:15 · The problem on one screen

**Window A · Admissions overview**

- Point at **10 applications**, **9 needs review**, **0 verified**, and the
  work queue on the right.
- Say: *“This is the admission desk before a person opens a single file. Ten
  applications, nine exceptions. The checker has already read every mark sheet,
  certificate and photograph, compared every subject, checked identity across
  documents, and applied the income, community and first-graduate rules.
  Everything here is deterministic — OCR, image measurements and fixed
  thresholds. No language model guesses a mark.”*

### 0:15–0:45 · The applicant's side and the happy path

**Window B · Your applications**

- Open the first record, the all-valid application (`MH26-22LXR`).
- Click **Run checks**.
- While it runs, say: *“Magic bytes decide the real file type. The sheet is
  rendered at 300 DPI and read with Tesseract using three segmentation modes;
  the best-scoring read wins. Fields are found geometrically, subjects are
  normalised with aliases and fuzzy matching, and every mark is compared with
  the entered value. The portrait goes through nine checks: resolution, aspect,
  orientation, file size, format, brightness, sharpness, exposure and face
  presence.”*
- When the panel says **Verified**, say: *“Four of four marks match, the printed
  name, register and year match, and every photo rule passes. No reviewer
  needed. The report unlocks.”*
- Click **Validation report**. Open the PDF.
- Say: *“The report is built by ReportLab from the stored run and findings — not
  a generated narrative. It carries the verdict, per-document verdicts, entered
  versus read marks, the identity consistency matrix, the supporting-document
  sections, measured photo values and the method note.”*
- Close the PDF.

### 0:45–1:00 · Mark mismatch

**Window A · Review queue → open Mark mismatch (`MH26-9JPYD`)**

- Point at the three reasons in the decision panel.
- Say: *“Three critical mismatches: Mathematics, 85 entered against 88 read;
  Physics, 78 against 81; Chemistry, 81 against 78. English matches. The
  extracted table shows the OCR confidence and the exact signed difference.
  This is the case that must never be auto-approved.”*

### 1:00–1:15 · Bad photograph

**Back → open Bad photograph (`MH26-BCHTZ`)**

- Point at the brightness row.
- Say: *“All four marks match. The only failure is the photograph: brightness
  27 out of 255 against a floor of 55. The face is present but the image is too
  dark to confirm identity, so it is critical and goes to a person.”*

### 1:15–1:30 · Missing subject

**Back → open Missing subject (`MH26-KUCYC`)**

- Point at the Physics row in the marks table.
- Say: *“Three of three entered marks match, but Physics is missing from the
  sheet. One critical missing-subject finding — the completeness rule does not
  repeat the same gap twice.”*

### 1:30–1:50 · Review queue and the human decision

**Back → Review queue**

- Say: *“Everything the checker cannot clear lands here. Nine open items: eight
  critical, one warning. The duplicate photograph sits last at standard
  priority because a reused file is a warning, not a rejection.”*
- Open **Bad photograph** (`MH26-BCHTZ`) again.
- Type in **Decision note**: `Called the applicant; identity confirmed against the register.`
- Say: *“The reviewer resolves the exception. A note is required. Approving
  records the reviewer, time and note, and moves the application to Approved —
  not silently to Verified.”*
- Click **Approve record**. Point at the recorded decision and the queue
  counters: **eight open, one decided**.

### 1:50–2:20 · Accuracy

**Window A · Accuracy**

- Point at the four target cards: **Field extraction 100%**, **Document fields
  100%**, **Mismatch recall 100%**, **Photo rule accuracy 100%**.
- Say: *“This is the reproducible synthetic benchmark, run through the real
  pipeline. Thirty mark sheets — 24 Class 12 and 6 Class 11 — plus 12
  supporting documents and 11 labelled photo fixtures. Every subject row was
  found and every mark read exactly: 130 of 130. Supporting-document fields:
  52 of 52. Document-type classification: 42 of 42, shown as a confusion matrix
  so OCR and classifier errors stay separable. Mean OCR confidence 95.6%, under
  a second per sheet.”*
- Point at the confusion matrix and the supporting-document table.
- Say: *“The evaluation uses the same thresholds as production and writes the
  same numbers to `backend/reports/accuracy.md`. No real student document is
  used anywhere.”*

### 2:20–2:50 · Extra documents

**Back → open Income above the limit (`MH26-AEB4R`)**

- Point at the annual-income row: **INR 320,000** against the **INR 250,000**
  limit. Say: *“This is a critical document finding, not a mark-sheet guess.”*

**Back → open Aadhaar checksum failure (`MH26-X9PTD`)**

- Point at **Aadhaar number XXXX XXXX 5185**.
- Say: *“The printed number fails the Verhoeff checksum. This is the only place
  the full number exists — encrypted at rest. The dashboard, API, PDF, logs and
  audit trail see only the last four.”*

**Back → open Class 11 vs Class 12 name (`MH26-9MMS3`)**

- Scroll to the **Identity consistency matrix**. Point at Name: Class 12 says
  **Ananya Subramanian** and matches; Class 11 says **Ananya Ramanathan** and
  does not.
- Say: *“The matrix compares the application, every mark sheet and every
  certificate. A father-name conflict is critical; an address difference is a
  warning. The Class 11 sheet, community certificate, expired income
  certificate and duplicate photo are all in the same queue if the judges want
  to see them.”*

### 2:50–3:00 · Audit and close

**Click Audit log**

- Say: *“The decision is appended to the audit log with the application
  reference, reviewer and note. The log is read-only from the product. The same
  trail carries validation runs, uploads, sign-ins and report downloads.”*
- Close: *“One hundred and forty backend tests. Fernet encryption at rest,
  Aadhaar masking, role-based access, ownership checks and login rate limiting.
  Deterministic by design.”*

---

## If something slips

| Symptom | Fix |
| --- | --- |
| App 1 already has a run | `python scripts/reset_demo.py`, then reload |
| App 3 is already approved | `python scripts/reset_demo.py` |
| Queue counts differ | `python scripts/reset_demo.py` |
| Accuracy page is empty | `python scripts/evaluate.py`, then reload |
| Report button still disabled | The run is still polling; wait two seconds or reload |
| PDF does not open | Download it from the button; the API also serves it at `/api/applications/{id}/report.pdf` |
| Tesseract error | Confirm the installed Tesseract path is available to the backend, then restart uvicorn |
| Running long | Skip the Aadhaar and Class 11 extra documents; keep the income example and the matrix |

**After the demo:** run `python scripts/reset_demo.py` to restore app 1 to
`submitted`, reopen the approved review, and clear sign-in/download noise from
the audit log. The references and the accuracy run do not change.

---

## Questions judges may ask

**Why not use an LLM?**
Marks must be repeatable and auditable. OCR confidence, pixel measurements and
thresholds produce the same result every run; an LLM can invent a mark or a
reason. No applicant data leaves the machine.

**How accurate is it?**
The reproducible synthetic evaluation covers 30 sheets across clean, noise,
blur, rotate, shadow and JPEG variants: 130/130 subject rows found, 130/130
marks exact, 18/18 injected mismatches found, 6/6 missing subjects found, 52/52
supporting-document fields exact, 42/42 document types classified, 20/20 photo
rule labels correct, 95.6% mean OCR confidence and under a second per sheet.

**What if a PDF is uploaded?**
PyMuPDF renders up to 12 pages at 300 DPI; magic bytes decide whether the file
is a PDF, JPEG or PNG before any parser runs. Mark sheets, Aadhaar cards and
certificates all share the same multi-page path.

**Does it recognise faces?**
No. It detects that a usable face is present and measures the image. Identity is
checked from printed names, dates of birth, register numbers and examination
years. The photograph is a document-quality check, not biometric matching; the
duplicate hash catches reused files.

**How is Aadhaar protected?**
The full synthetic number is stored only in the encrypted `AadhaarRecord`.
Every other layer sees `XXXX XXXX 1234`; the checksum and QR are evaluated
inside the validator before the number is discarded from the response. No real
Aadhaar number or real document exists in this repository.

**What is production-hardening work?**
College ERP integration, more board layouts and languages, consent/retention
policy, and liveness or anti-spoofing if photographs become part of identity
verification. The correction workflow is already admin-only, audited and
re-runs validation with corrections preserved.

**Where are the security controls?**
JWT auth with bcrypt hashes, student/admin RBAC and ownership checks on every
record, Fernet-encrypted uploads and Aadhaar numbers at rest, magic-byte
validation, a login rate limit, `no-store` on report downloads, and an
append-only audit trail for sign-ins, uploads, validation runs, downloads and
review decisions.
