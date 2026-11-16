"""Accuracy evaluation over the synthetic corpus.

The evaluator is deliberately separate from the request path: it runs the real
OCR pipeline, the real comparison engine and the real photo rules, then scores
each against ground truth. Nothing here feeds production validation results.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import REPORTS_DIR, SYNTHETIC_DIR, rules
from app.db.session import get_session_factory
from app.models.accuracy import AccuracyRun
from app.ocr.extract import extract_document
from app.ocr.types import SubjectRow
from app.services.comparison import EnteredMarkValue, compare_marks
from app.services.subjects import clean, normalize_subject
from app.services.synthetic import ensure_dataset
from app.validators.photo import analyze_photo


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _subject_key(value: Any) -> str:
    return clean(normalize_subject(str(value or "")).canonical)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 1.0


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _truth_rows(case: dict[str, Any]) -> list[SubjectRow]:
    return [
        SubjectRow(
            subject_raw=row["subject"],
            marks_obtained=float(row["marks"]),
            max_marks=float(row["max_marks"]) if row["max_marks"] is not None else None,
            grade=row.get("grade"),
            confidence=100.0,
            page=1,
        )
        for row in case["subjects"]
    ]


def _entered(case: dict[str, Any]) -> list[EnteredMarkValue]:
    return [
        EnteredMarkValue(
            subject=row["subject"],
            marks=float(row["marks"]),
            max_marks=float(row["max_marks"]) if row["max_marks"] is not None else None,
        )
        for row in case["entered"]
    ]


def _detected_results(result) -> tuple[set[str], set[str]]:
    mismatched = {
        _subject_key(check.subject_norm or check.field)
        for check in result.checks
        if check.result == "mismatch"
    }
    missing = {
        _subject_key(check.subject_norm or check.field)
        for check in result.checks
        if check.result == "missing_upload"
    }
    return mismatched, missing


def _score_photos(dataset: dict[str, Any]) -> dict[str, Any]:
    fixture_rows = []
    rule_correct: dict[str, int] = {}
    rule_total: dict[str, int] = {}
    critical_correct = 0
    labels_correct = 0
    labels_total = 0

    for fixture in dataset["photos"]:
        path = SYNTHETIC_DIR / fixture["file"]
        actual: dict[str, str] = {}
        critical: list[str] = []
        error = None
        faces = None
        try:
            analysis = analyze_photo(path.read_bytes(), fixture["mime"])
            actual = {
                check.field: ("pass" if check.passed else "fail") for check in analysis.checks
            }
            critical = sorted(
                check.field
                for check in analysis.checks
                if not check.passed and check.severity == "critical"
            )
            faces = analysis.metrics.get("faces")
        except Exception as exc:  # noqa: BLE001 - a failed fixture must be reported
            error = f"{type(exc).__name__}: {exc}"

        wrong = []
        for field_name, expected in fixture["expected"].items():
            rule_total[field_name] = rule_total.get(field_name, 0) + 1
            labels_total += 1
            if actual.get(field_name) == expected:
                rule_correct[field_name] = rule_correct.get(field_name, 0) + 1
                labels_correct += 1
            else:
                wrong.append(f"{field_name}: expected {expected}, read {actual.get(field_name)}")

        expected_critical = sorted(fixture.get("expected_critical", []))
        critical_ok = critical == expected_critical
        if critical_ok:
            critical_correct += 1

        fixture_rows.append(
            {
                "id": fixture["id"],
                "note": fixture["note"],
                "expected": fixture["expected"],
                "actual": actual,
                "faces": faces,
                "expected_critical": expected_critical,
                "actual_critical": critical,
                "critical_match": critical_ok,
                "wrong": wrong,
                "error": error,
            }
        )

    rule_rows = [
        {
            "rule": field_name,
            "tested": rule_total[field_name],
            "correct": rule_correct.get(field_name, 0),
            "accuracy": _ratio(rule_correct.get(field_name, 0), rule_total[field_name]),
        }
        for field_name in sorted(rule_total)
    ]
    return {
        "rule_accuracy": _ratio(labels_correct, labels_total),
        "labels_correct": labels_correct,
        "labels_total": labels_total,
        "critical_accuracy": _ratio(critical_correct, len(fixture_rows)),
        "critical_correct": critical_correct,
        "fixtures": len(fixture_rows),
        "rules": rule_rows,
        "cases": fixture_rows,
    }


def evaluate_dataset(dataset: dict[str, Any]) -> tuple[dict[str, Any], str]:
    config = rules()["evaluation"]
    cases = dataset["cases"]
    case_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    name_ok = register_ok = year_ok = 0
    subjects_found = marks_exact = rows_exact = max_exact = 0
    subjects_total = 0
    confidence_values: list[float] = []
    duration_values: list[int] = []

    mismatch_tp = mismatch_fp = mismatch_fn = 0
    case_tp = case_fp = case_fn = case_tn = 0
    engine_tp = engine_fp = engine_fn = 0
    missing_tp = missing_fp = missing_fn = 0
    extra_expected = extra_detected = 0

    variant_stats: dict[str, dict[str, float]] = {}

    for case in cases:
        variant = case["variant"]
        stats = variant_stats.setdefault(
            variant,
            {
                "cases": 0,
                "identity_hits": 0,
                "identity_total": 0,
                "subjects_found": 0,
                "subjects_total": 0,
                "marks_exact": 0,
                "confidence_sum": 0.0,
                "confidence_n": 0,
            },
        )
        stats["cases"] += 1

        truth_by_key = {
            _subject_key(row["subject"]): row for row in case["subjects"]
        }
        truth_marks = {
            key: float(row["marks"]) for key, row in truth_by_key.items()
        }
        subjects_total += len(truth_marks)
        stats["subjects_total"] += len(truth_marks)
        stats["identity_total"] += 3
        expected_mismatches = {_subject_key(item["subject"]) for item in case["expected"]["mismatches"]}
        expected_missing = {_subject_key(item) for item in case["expected"]["missing_upload"]}
        expected_extra = {_subject_key(item) for item in case["expected"]["extra_on_sheet"]}

        row = {
            "id": case["id"],
            "variant": variant,
            "expected_mismatches": sorted(expected_mismatches),
            "detected_mismatches": [],
            "expected_missing": sorted(expected_missing),
            "detected_missing": [],
            "name_ok": False,
            "register_ok": False,
            "year_ok": False,
            "subjects_found": 0,
            "subjects_total": len(truth_marks),
            "marks_exact": 0,
            "rows_exact": 0,
            "confidence": 0.0,
            "duration_ms": 0,
            "error": None,
        }

        try:
            raw = (SYNTHETIC_DIR / case["sheet"]).read_bytes()
            extraction = extract_document(raw, case["mime"])
        except Exception as exc:  # noqa: BLE001 - report, do not abort the run
            message = f"{type(exc).__name__}: {exc}"
            row["error"] = message
            errors.append({"case": case["id"], "variant": variant, "error": message})
            case_rows.append(row)
            continue

        duration_values.append(extraction.duration_ms)
        name_match = _text(extraction.name.value) == _text(case["applicant_name"])
        register_match = _identifier(extraction.register_number.value) == _identifier(
            case["register_number"]
        )
        year_match = str(extraction.exam_year.value) == str(case["exam_year"])
        name_ok += int(name_match)
        register_ok += int(register_match)
        year_ok += int(year_match)
        stats["identity_hits"] += int(name_match) + int(register_match) + int(year_match)
        row["name_ok"] = name_match
        row["register_ok"] = register_match
        row["year_ok"] = year_match

        extracted: dict[str, SubjectRow] = {}
        for subject_row in extraction.subjects:
            key = _subject_key(subject_row.subject_raw)
            if key not in extracted or subject_row.confidence > extracted[key].confidence:
                extracted[key] = subject_row
        if extraction.subjects:
            row_confidence = statistics.mean(item.confidence for item in extraction.subjects)
            confidence_values.append(row_confidence)
            stats["confidence_sum"] += row_confidence
            stats["confidence_n"] += 1
            row["confidence"] = round(row_confidence, 1)

        wrong_marks = []
        missing_subjects = []
        for key, truth_mark in truth_marks.items():
            subject_row = extracted.get(key)
            if subject_row is None:
                missing_subjects.append(key)
                continue
            subjects_found += 1
            stats["subjects_found"] += 1
            row["subjects_found"] += 1
            truth_max = truth_by_key[key]["max_marks"]
            max_ok = (
                subject_row.max_marks is not None
                and truth_max is not None
                and abs(subject_row.max_marks - float(truth_max)) < 1e-9
            )
            if max_ok:
                max_exact += 1
            if subject_row.marks_obtained is not None and abs(subject_row.marks_obtained - truth_mark) < 1e-9:
                marks_exact += 1
                stats["marks_exact"] += 1
                row["marks_exact"] += 1
                if max_ok:
                    rows_exact += 1
            else:
                wrong_marks.append(
                    {"subject": key, "expected": truth_mark, "read": subject_row.marks_obtained}
                )

        result = compare_marks(_entered(case), extraction.subjects)
        detected_mismatches, detected_missing = _detected_results(result)
        row["detected_mismatches"] = sorted(detected_mismatches)
        row["detected_missing"] = sorted(detected_missing)

        mismatch_tp += len(expected_mismatches & detected_mismatches)
        mismatch_fp += len(detected_mismatches - expected_mismatches)
        mismatch_fn += len(expected_mismatches - detected_mismatches)
        expected_any = bool(expected_mismatches)
        detected_any = bool(detected_mismatches)
        case_tp += int(expected_any and detected_any)
        case_fp += int(not expected_any and detected_any)
        case_fn += int(expected_any and not detected_any)
        case_tn += int(not expected_any and not detected_any)

        missing_tp += len(expected_missing & detected_missing)
        missing_fp += len(detected_missing - expected_missing)
        missing_fn += len(expected_missing - detected_missing)
        extra_expected += len(expected_extra)
        extra_detected += int(result.extra)

        # A second pass on ground-truth rows isolates the comparison rules from
        # OCR error, so a low end-to-end score points at the right layer.
        engine_result = compare_marks(_entered(case), _truth_rows(case))
        engine_mismatches, _ = _detected_results(engine_result)
        engine_tp += len(expected_mismatches & engine_mismatches)
        engine_fp += len(engine_mismatches - expected_mismatches)
        engine_fn += len(expected_mismatches - engine_mismatches)

        row["wrong_marks"] = wrong_marks[:4]
        row["missing_subjects"] = missing_subjects[:4]
        if wrong_marks or missing_subjects:
            errors.append(
                {
                    "case": case["id"],
                    "variant": variant,
                    "error": "extraction mismatch",
                    "missing_subjects": missing_subjects,
                    "wrong_marks": wrong_marks,
                }
            )
        case_rows.append(row)

    total = len(cases)
    identity_total = total * 3
    field_accuracy = _ratio(name_ok + register_ok + year_ok, identity_total)
    mismatch_metrics = _prf(mismatch_tp, mismatch_fp, mismatch_fn)
    engine_metrics = _prf(engine_tp, engine_fp, engine_fn)
    missing_metrics = _prf(missing_tp, missing_fp, missing_fn)
    photo = _score_photos(dataset)

    variant_rows = []
    for variant, stats in variant_stats.items():
        mean_confidence = (
            round(stats["confidence_sum"] / stats["confidence_n"], 1)
            if stats["confidence_n"]
            else 0.0
        )
        variant_rows.append(
            {
                "variant": variant,
                "cases": int(stats["cases"]),
                "identity_accuracy": _ratio(stats["identity_hits"], stats["identity_total"]),
                "subject_recall": _ratio(stats["subjects_found"], stats["subjects_total"]),
                "mark_accuracy": _ratio(stats["marks_exact"], stats["subjects_total"]),
                "mean_confidence": mean_confidence,
            }
        )
    variant_rows.sort(key=lambda item: item["variant"])

    targets = {
        "field_accuracy": float(config["min_field_accuracy"]),
        "mismatch_recall": float(config["min_mismatch_recall"]),
        "photo_rule_accuracy": float(config["min_photo_accuracy"]),
    }
    target_checks = {
        "field_accuracy": {
            "value": field_accuracy,
            "target": targets["field_accuracy"],
            "met": field_accuracy >= targets["field_accuracy"],
        },
        "mismatch_recall": {
            "value": mismatch_metrics["recall"],
            "target": targets["mismatch_recall"],
            "met": mismatch_metrics["recall"] >= targets["mismatch_recall"],
        },
        "photo_rule_accuracy": {
            "value": photo["rule_accuracy"],
            "target": targets["photo_rule_accuracy"],
            "met": photo["rule_accuracy"] >= targets["photo_rule_accuracy"],
        },
    }

    summary = {
        "status": "completed",
        "dataset": dataset["dataset"],
        "cases": total,
        "field_accuracy": field_accuracy,
        "fields": {
            "name": _ratio(name_ok, total),
            "register_number": _ratio(register_ok, total),
            "exam_year": _ratio(year_ok, total),
        },
        "subjects": {
            "total": subjects_total,
            "found": subjects_found,
            "found_rate": _ratio(subjects_found, subjects_total),
            "marks_exact": marks_exact,
            "mark_accuracy": _ratio(marks_exact, subjects_total),
            "rows_exact": rows_exact,
            "max_marks_exact": max_exact,
        },
        "mismatch": {
            **mismatch_metrics,
            "tp": mismatch_tp,
            "fp": mismatch_fp,
            "fn": mismatch_fn,
            "matrix": {
                "tp": case_tp,
                "fp": case_fp,
                "fn": case_fn,
                "tn": case_tn,
                "accuracy": _ratio(case_tp + case_tn, total),
            },
        },
        "comparison_engine": {
            **engine_metrics,
            "tp": engine_tp,
            "fp": engine_fp,
            "fn": engine_fn,
        },
        "missing": {
            **missing_metrics,
            "tp": missing_tp,
            "fp": missing_fp,
            "fn": missing_fn,
        },
        "extras": {"expected": extra_expected, "detected": extra_detected},
        "ocr_confidence": round(statistics.mean(confidence_values), 1) if confidence_values else 0.0,
        "mean_duration_ms": int(statistics.mean(duration_values)) if duration_values else 0,
        "photos": photo,
        "variants": variant_rows,
        "targets": target_checks,
        "cases_detail": case_rows,
        "errors": errors[:12],
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    return summary, _markdown(summary)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Accuracy evaluation",
        "",
        f"Dataset **{summary['dataset']}** · {summary['cases']} synthetic mark sheets · "
        f"{summary['photos']['fixtures']} labelled photo fixtures.",
        "",
        "Deterministic pipeline: Tesseract OCR, rule-based comparison and measured photo rules. "
        "No generative model is involved at any stage.",
        "",
        "## Headline",
        "",
        "| Measure | Result | Target | Status |",
        "| --- | ---: | ---: | --- |",
    ]
    labels = {
        "field_accuracy": "Field extraction (name, register, year)",
        "mismatch_recall": "Mismatch detection recall",
        "photo_rule_accuracy": "Photo rule accuracy",
    }
    for key, label in labels.items():
        check = summary["targets"][key]
        lines.append(
            f"| {label} | {_percent(check['value'])} | {_percent(check['target'])} | "
            f"{'met' if check['met'] else 'below target'} |"
        )
    lines += [
        "",
        f"Subject rows found: **{_percent(summary['subjects']['found_rate'])}** · "
        f"Obtained marks exact: **{_percent(summary['subjects']['mark_accuracy'])}** · "
        f"Mean row confidence: **{summary['ocr_confidence']}%**.",
        "",
        "## Mark verification",
        "",
        "| Layer | Precision | Recall | F1 | TP / FP / FN |",
        "| --- | ---: | ---: | ---: | --- |",
        f"| End to end (OCR + rules) | {_percent(summary['mismatch']['precision'])} | "
        f"{_percent(summary['mismatch']['recall'])} | {_percent(summary['mismatch']['f1'])} | "
        f"{summary['mismatch']['tp']} / {summary['mismatch']['fp']} / {summary['mismatch']['fn']} |",
        f"| Rules on ground-truth rows | {_percent(summary['comparison_engine']['precision'])} | "
        f"{_percent(summary['comparison_engine']['recall'])} | "
        f"{_percent(summary['comparison_engine']['f1'])} | "
        f"{summary['comparison_engine']['tp']} / {summary['comparison_engine']['fp']} / "
        f"{summary['comparison_engine']['fn']} |",
        "",
        "## Extraction by degradation",
        "",
        "| Variant | Cases | Identity | Subject rows | Marks exact | Mean confidence |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["variants"]:
        lines.append(
            f"| {row['variant']} | {row['cases']} | {_percent(row['identity_accuracy'])} | "
            f"{_percent(row['subject_recall'])} | {_percent(row['mark_accuracy'])} | "
            f"{row['mean_confidence']}% |"
        )
    lines += [
        "",
        "## Photo rules",
        "",
        f"Labelled rule outcomes: **{summary['photos']['labels_correct']}/"
        f"{summary['photos']['labels_total']}** correct · critical-failure sets: "
        f"**{summary['photos']['critical_correct']}/{summary['photos']['fixtures']}** exact.",
        "",
        "| Rule | Fixtures | Correct | Accuracy |",
        "| --- | ---: | ---: | ---: |",
    ]
    for rule_row in summary["photos"]["rules"]:
        lines.append(
            f"| {rule_row['rule']} | {rule_row['tested']} | {rule_row['correct']} | "
            f"{_percent(rule_row['accuracy'])} |"
        )
    if summary["errors"]:
        lines += ["", "## Cases needing attention", ""]
        for error in summary["errors"]:
            lines.append(f"- **{error['case']}** ({error['variant']}): {error['error']}")
    lines += [
        "",
        "## Method",
        "",
        "- Mark sheets are generated from a fixed seed with fictional identities and known marks.",
        "- Variants add grain, blur, a slight tilt, uneven light and JPEG compression.",
        "- Mismatch labels come from the generated entry, never from the OCR output.",
        "- Photo expectations are set by the controlled perturbation; every rule is measured "
        "against the same thresholds used in production.",
        "- Face detection is a Haar cascade heuristic and is reported as a warning, not a rejection.",
        "",
    ]
    return "\n".join(lines)


def _store(
    db,
    *,
    dataset_name: str,
    total_cases: int,
    summary: dict[str, Any],
    report_md: str,
    created_by: int | None,
) -> AccuracyRun:
    run = AccuracyRun(
        dataset=dataset_name,
        total_cases=total_cases,
        summary=summary,
        report_md=report_md,
        created_by=created_by,
    )
    db.add(run)
    db.flush()
    return run


def run_evaluation(run_id: int | None = None, created_by: int | None = None) -> int:
    """Run the full evaluation, update the AccuracyRun row, and write the report.

    When `run_id` is supplied the row was already created in `running` state by
    the API route; otherwise a fresh row is stored (CLI use).
    """

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "accuracy.md"
    factory = get_session_factory()
    with factory() as db:
        run = db.get(AccuracyRun, run_id) if run_id is not None else None
        if run is None:
            run = _store(
                db,
                dataset_name=rules()["evaluation"]["dataset"],
                total_cases=0,
                summary={
                    "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
                report_md="",
                created_by=created_by,
            )
            db.commit()
            run_id = run.id

        try:
            dataset = ensure_dataset()
            summary, markdown = evaluate_dataset(dataset)
            summary["started_at"] = (run.summary or {}).get("started_at")
            run.dataset = dataset["dataset"]
            run.total_cases = len(dataset["cases"])
            run.summary = summary
            run.report_md = markdown
            report_path.write_text(markdown, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - a failed evaluation is data too
            failed = {
                "status": "failed",
                "dataset": run.dataset,
                "error": f"{type(exc).__name__}: {exc}",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            run.summary = failed
            run.total_cases = 0
            run.report_md = f"# Accuracy evaluation failed\n\n{failed['error']}\n"
            report_path.write_text(run.report_md, encoding="utf-8")
        db.commit()
        return int(run_id)


def latest_run_summary(run: AccuracyRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    summary = run.summary or {}
    return {
        "id": run.id,
        "dataset": run.dataset,
        "total_cases": run.total_cases,
        "status": summary.get("status", "completed"),
        "summary": summary,
        "created_at": run.created_at.isoformat(),
        "report_path": str(Path("reports") / "accuracy.md"),
    }
