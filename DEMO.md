# Maatram Verify — three-minute demo

**Problem MH26-01 · Smart Admission Document Validation**

Five applications arrive with a mark sheet and a photograph. The checker reads
the sheet, compares every entered subject, measures the portrait, detects
duplicates and identity gaps, and sends only the exceptions to a person. Every
result is produced by Tesseract, OpenCV/Pillow, regex, rapidfuzz and fixed rules.
No generative model touches a decision.

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

The current database is already seeded. The five records are:

| Student | Programme | Reference | State |
| --- | --- | --- | --- |
| Ananya | B.Sc. Computer Science | `MH26-5PCPR` | Submitted — no run yet |
| Ananya | B.E. Electronics and Communication | `MH26-AZ3GX` | Needs review — 3 mark mismatches |
| Rohan | B.Sc. Computer Science | `MH26-TDVAY` | Needs review — dark photo |
| Rohan | B.Sc. Physical Sciences | `MH26-V7THG` | Needs review — Physics missing |
| Ananya | B.Sc. Data Science | `MH26-Y4SFD` | Needs review — duplicate photo |

The queue has **4 open items**: three critical (priority 20) and one standard
warning (priority 50). If the demo has been run before, restore this state:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\reset_demo.py
```

Do **not** run `seed.py --reset` immediately before a demo: it generates new
references. The reset script above keeps the references stable. If you seed a
fresh clone, use the references printed by the seed.

---

## Run of show

### 0:00–0:20 · The problem on one screen

**Window A · Admissions overview**

- Point at **5 applications**, **4 needs review**, **0 verified**, and **4 findings**.
- Say: *“This is the admission desk before a person opens a single file. Five
  applications, four exceptions. The checker has already read every mark sheet,
  compared every subject, tested every photograph and checked for duplicates.
  Everything here is deterministic — OCR, image rules and fixed thresholds. No
  language model guesses a mark.”*

### 0:20–0:30 · The applicant's side

**Window B · Your applications**

- Point at Ananya's three records: one clean, one with mismatches, one duplicate.
- Say: *“The applicant sees the same truth. I'll take the clean record and run
  it live.”*
- Open **B.Sc. Computer Science** (`MH26-5PCPR`).

### 0:30–1:05 · Happy path: verified without a person

**Window B · Application detail**

- Click **Run checks**.
- While it runs, say: *“Magic bytes decide the real file type, not the extension.
  The sheet is rendered at 300 DPI and read with Tesseract using three
  segmentation modes; the best-scoring read wins. Fields are found
  geometrically, subjects are normalised with aliases and fuzzy matching, and
  every mark is compared with the entered value. The portrait goes through nine
  checks: resolution, aspect, orientation, file size, format, brightness,
  sharpness, exposure and face presence.”*
- When the panel says **Verified**, say: *“Four of four marks match, the printed
  name, register and year match, and every photo rule passes. No reviewer
  needed. The report button unlocks.”*
- Click **Validation report**. Open the downloaded PDF from the browser shelf.
- Say: *“Two pages, built by ReportLab from the stored run and findings — not a
  generated narrative. Verdict, entered-versus-read marks, identity, document
  inventory, measured photo values and the method note. Reference and timestamp
  make it auditable.”*
- Close the PDF.

### 1:05–1:15 · The queue

**Window A · Review queue**

- Click **Review queue**.
- Say: *“Everything the checker cannot clear lands here. Critical findings
  first, then warnings. Four open items.”*

### 1:15–1:33 · Mark mismatch

**Open B.E. Electronics and Communication (`MH26-AZ3GX`)**

- Point at the three reasons in the decision panel.
- Say: *“Three critical mismatches: Mathematics, 85 entered against 88 read;
  Physics, 78 against 81; Chemistry, 81 against 78. English matches. The
  extracted table shows the OCR confidence and the exact signed difference.
  This is the case that must never be auto-approved.”*

### 1:33–1:48 · Bad photograph

**Back → open B.Sc. Computer Science, Rohan (`MH26-TDVAY`)**

- Point at the brightness row.
- Say: *“All four marks match. The only failure is the photograph: brightness
  27 out of 255 against a floor of 55. The face is present but the image is too
  dark to confirm identity, so it is critical and goes to a person.”*

### 1:48–2:03 · Missing subject

**Back → open B.Sc. Physical Sciences (`MH26-V7THG`)**

- Point at the Physics row in the marks table.
- Say: *“Three of three entered marks match, but Physics is missing from the
  sheet. One critical missing-subject finding — the completeness rule does not
  repeat the same gap twice.”*

### 2:03–2:13 · Duplicate photograph

**Back → point at the fourth queue row, B.Sc. Data Science (`MH26-Y4SFD`)**

- Do not open it unless you have spare time.
- Say: *“The last item passes all four mark checks. Its photo is a duplicate of
  another upload on the same account — SHA-256 and perceptual hash agree. That
  is a warning, not a rejection, so it sits at standard priority and still gets
  a human look.”*

### 2:13–2:40 · Human in the loop

**Back → open B.Sc. Computer Science, Rohan (`MH26-TDVAY`) again**

- Type in **Decision note**: `Called the applicant; identity confirmed against the register.`
- Say: *“The reviewer resolves the exception. A note is required. Approving
  records the reviewer, time and note, and moves the application to Approved —
  not silently to Verified. The queue now has three open and one decided.”*
- Click **Approve record**.
- Point at the recorded decision and the queue counters.

### 2:40–2:52 · Audit

**Click Audit log**

- Say: *“The decision is appended to the audit log with the application
  reference, reviewer and note. The log is read-only from the product. The same
  trail carries validation runs, sign-ins and report downloads.”*

### 2:52–3:00 · Close

- Say: *“On the synthetic benchmark: 24 cases, 104 of 104 subjects read, 100%
  field extraction, 100% mismatch recall and 100% photo-rule accuracy. Seventy-
  three backend tests. Fernet encryption at rest, role-based access, ownership
  checks and login rate limiting. Deterministic by design.”*

---

## If something slips

| Symptom | Fix |
| --- | --- |
| App 1 already has a run | `python scripts/reset_demo.py`, then reload |
| App 3 is already approved | `python scripts/reset_demo.py` |
| Queue counts differ | `python scripts/reset_demo.py` |
| Report button still disabled | The run is still polling; wait two seconds or reload |
| PDF does not open | Download it from the button; the API also serves it at `/api/applications/{id}/report.pdf` |
| Tesseract error | Confirm the installed Tesseract path is available to the backend, then restart uvicorn |
| Running long | Skip opening the duplicate record; cut the PDF page-2 description and the benchmark close to one sentence |

**After the demo:** run `python scripts/reset_demo.py` to restore app 1 to
`submitted`, reopen the review decision, and clear sign-in/download noise from
the audit log. The references do not change.

---

## Questions judges may ask

**Why not use an LLM?**
Marks must be repeatable and auditable. OCR confidence, pixel measurements and
thresholds produce the same result every run; an LLM can invent a mark or a
reason. No applicant data leaves the machine.

**How accurate is it?**
The reproducible synthetic evaluation covers 24 sheets across clean, noise,
blur, rotate, shadow and JPEG variants: 100% field extraction, 104/104 subjects
found, 104/104 marks exact, 100% mismatch recall, 100% photo-rule accuracy,
95.6% mean OCR confidence and roughly 0.7 seconds per sheet.

**What if a PDF is uploaded?**
PyMuPDF renders up to 12 pages at 300 DPI; magic bytes decide whether the file
is a PDF, JPEG or PNG before any parser runs. The mark-sheet path handles a
multi-page document.

**Does it recognise faces?**
No. It detects that a usable face is present and measures the image. Identity is
checked from the printed name, register number and examination year. The
photograph is a document-quality check, not biometric matching; the duplicate
hash catches reused files.

**What is production-hardening work?**
College ERP integration, more board layouts and languages, a correction workflow
for extracted marks, retention/consent policy, and liveness or anti-spoofing if
photographs become part of identity verification.

**Where are the security controls?**
JWT auth with bcrypt hashes, student/admin RBAC and ownership checks on every
record, Fernet-encrypted uploads at rest, magic-byte validation, a login rate
limit, `no-store` on report downloads, and an append-only audit trail for
sign-ins, uploads, validation runs, downloads and review decisions.
