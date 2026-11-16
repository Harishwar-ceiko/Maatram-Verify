from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import mean

from app.ocr.types import Extraction, Field, OcrPage, SubjectRow, Word

ALPHA = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"\d")
GRADE = re.compile(r"^(?:[A-Fa-f][+-]?|PASS|FAIL)$")
YEAR = re.compile(r"\b(19|20)\d{2}\b")

NAME_LABELS = ("candidate", "name", "applicant", "student")
REGISTER_LABELS = ("register", "reg", "roll", "enrolment", "enrollment", "enroll")
LABEL_NOISE = {"no", "no.", "number", "num", "name", "candidate", "register", "reg", "roll"}
TABLE_WORDS = {
    "subject",
    "subjects",
    "maximum",
    "max",
    "obtained",
    "marks",
    "mark",
    "grade",
    "total",
}
STOP_WORDS = {"grand", "total", "result", "pass", "fail", "controller", "examinations"}


@dataclass(slots=True)
class Row:
    words: list[Word]
    top: int
    bottom: int
    left: int
    right: int

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


def visual_rows(words: list[Word]) -> list[Row]:
    """Merge engine lines that sit on the same visual baseline.

    Tesseract sometimes splits a printed row into several line records, and a
    table row must be handled as one row regardless of that.
    """

    usable = [word for word in words if word.text.strip()]
    if not usable:
        return []
    heights = sorted(word.height for word in usable if word.height > 0)
    median_height = heights[len(heights) // 2] if heights else 12
    # Tesseract's line boxes drift by a few pixels even after deskew. Merge on a
    # share of the glyph height, while staying well below table row pitch (74px
    # in the generated statements).
    tolerance = max(10.0, median_height * 1.15)

    groups: list[list[Word]] = []
    for word in sorted(usable, key=lambda item: (item.center_y, item.left)):
        if groups and abs(word.center_y - mean(item.center_y for item in groups[-1])) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])

    rows: list[Row] = []
    for group in groups:
        ordered = sorted(group, key=lambda item: item.left)
        rows.append(
            Row(
                words=ordered,
                top=min(word.top for word in ordered),
                bottom=max(word.bottom for word in ordered),
                left=min(word.left for word in ordered),
                right=max(word.right for word in ordered),
            )
        )
    return sorted(rows, key=lambda row: (row.top, row.left))


def _clean_token(text: str) -> str:
    return text.strip(".,:;()[]{}|").lower()


def _alpha_ratio(word: Word) -> float:
    letters = len(ALPHA.findall(word.text))
    return letters / max(1, len(word.text))


def _is_label(text: str, labels: tuple[str, ...]) -> bool:
    # Exact tokens only: "REG2026A014" must never be mistaken for a "reg" label.
    return _clean_token(text) in labels


def parse_marks(text: str) -> float | None:
    """Read a printed mark without inventing precision.

    Tesseract occasionally confuses O/0, l/1 and I/1 in a numeric column. Those
    substitutions are safe inside a digits-only field. A prose word such as
    "REG2026C001" or "evaluation" must never be turned into a number, so the
    token has to look numeric before any substitution happens.
    """

    token = text.strip().strip(".,:;()[]{}|%")
    if not token:
        return None
    if re.search(r"[A-Za-z]", token) and not re.fullmatch(r"[0-9OoIl.,%eE]+", token):
        return None

    cleaned = token.replace(",", "")
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace("l", "1").replace("I", "1")
    cleaned = cleaned.replace("e", "0").replace("E", "0")
    match = re.search(r"\d{1,4}(?:\.\d{1,2})?", cleaned)
    if not match:
        return None
    value = float(match.group())
    if 0 <= value <= 1000:
        return value
    return None


def _confidence(words: list[Word]) -> float:
    usable = [word.confidence for word in words if word.confidence > 0]
    return round(mean(usable), 1) if usable else 0.0


def _is_table_header(row: Row) -> bool:
    tokens = {_clean_token(word.text) for word in row.words}
    has_subject = "subject" in tokens or "subjects" in tokens
    has_marks = bool(tokens & {"maximum", "max", "obtained", "marks", "grade"})
    return has_subject and has_marks


def _header_columns(row: Row) -> dict[str, float]:
    columns: dict[str, float] = {}
    for word in row.words:
        token = _clean_token(word.text)
        if token in {"subject", "subjects"}:
            columns.setdefault("subject", word.center_x)
        elif token.startswith("max"):
            columns.setdefault("max", word.center_x)
        elif token.startswith("obtain") or token in {"marks", "mark", "score"}:
            columns.setdefault("obtained", word.center_x)
        elif token.startswith("grade"):
            columns.setdefault("grade", word.center_x)
    return columns


def _assign_columns(row: Row, columns: dict[str, float]) -> dict[str, list[Word]]:
    assigned: dict[str, list[Word]] = {name: [] for name in columns}
    for word in row.words:
        nearest = min(columns, key=lambda name: abs(word.center_x - columns[name]))
        assigned[nearest].append(word)
    return assigned


def _row_subject(words: list[Word]) -> str:
    kept = [word.text for word in words if ALPHA.search(word.text) and not DIGIT.search(word.text)]
    return " ".join(kept).strip()


def _grade(words: list[Word]) -> str | None:
    for word in words:
        token = word.text.strip()
        if GRADE.match(token):
            return token.upper()
    return None


def _first_mark(words: list[Word], *, prefer: str | None = None) -> tuple[float | None, Word | None]:
    ordered = words
    if prefer == "right":
        ordered = sorted(words, key=lambda word: word.left, reverse=True)
    for word in ordered:
        # A numeric column can contain a misread O/0, l/1 or I/1. It cannot
        # contain a whole prose word: without this guard "evaluation" parses as
        # "1" and a footer sentence becomes a subject row.
        token = word.text.strip(".,:;()[]{}|%")
        if not token or len(token) > 7 or not DIGIT.search(token):
            continue
        if not re.fullmatch(r"[0-9OoIl.,%eE]+", token):
            continue
        value = parse_marks(token)
        if value is not None:
            return value, word
    return None, None


def _subject_row(row: Row, columns: dict[str, float], page: int) -> SubjectRow | None:
    if _is_table_header(row):
        return None

    if columns:
        assigned = _assign_columns(row, columns)
        subject_words = [word for word in assigned.get("subject", []) if _alpha_ratio(word) > 0.4]
        obtained, obtained_word = _first_mark(assigned.get("obtained", []))
        max_marks, max_word = _first_mark(assigned.get("max", []))
        grade = _grade(assigned.get("grade", []))
        evidence = subject_words + [word for word in (obtained_word, max_word) if word]
    else:
        words = sorted(row.words, key=lambda word: word.left)
        subject_words = []
        numbers: list[tuple[float, Word]] = []
        trailing: list[Word] = []
        for word in words:
            if DIGIT.search(word.text):
                value = parse_marks(word.text)
                if value is not None:
                    numbers.append((value, word))
                else:
                    trailing.append(word)
            elif not numbers:
                if _alpha_ratio(word) > 0.4:
                    subject_words.append(word)
            else:
                trailing.append(word)
        if len(numbers) >= 2:
            max_marks, max_word = numbers[0]
            obtained, obtained_word = numbers[1]
        elif numbers:
            max_marks, max_word = None, None
            obtained, obtained_word = numbers[0]
        else:
            return None
        grade = _grade(trailing)
        evidence = subject_words + [word for word in (obtained_word, max_word) if word]

    subject = _row_subject(subject_words)
    if len(ALPHA.findall(subject)) < 2:
        return None
    subject_token = _clean_token(subject)
    if any(word in subject_token.split() for word in STOP_WORDS) or "total" in subject_token:
        return None
    if subject_token in TABLE_WORDS or subject_token.startswith("subject"):
        return None
    if obtained is None and max_marks is None:
        return None

    return SubjectRow(
        subject_raw=" ".join(subject.split()),
        marks_obtained=obtained,
        max_marks=max_marks,
        grade=grade,
        confidence=_confidence(evidence),
        page=page,
        bbox={"left": row.left, "top": row.top, "right": row.right, "bottom": row.bottom},
    )


def extract_subjects(pages: list[OcrPage]) -> list[SubjectRow]:
    rows_out: list[SubjectRow] = []
    seen: set[tuple[str, float | None, float | None]] = set()

    for page in pages:
        rows = visual_rows(page.words)
        columns: dict[str, float] = {}
        for row in rows:
            if _is_table_header(row):
                columns = _header_columns(row)
                continue
            if not columns and len(rows_out) == 0:
                # No header: try a table-shaped row rather than giving up. This
                # is the line-based fallback for sparse statements.
                pass
            subject = _subject_row(row, columns, page.number)
            if subject is None:
                continue
            key = (_clean_token(subject.subject_raw), subject.marks_obtained, subject.max_marks)
            if key in seen:
                continue
            seen.add(key)
            rows_out.append(subject)

    return rows_out


def _row_value(
    rows: list[Row],
    anchor_word: Word,
    anchor_row: Row,
    *,
    left_bound: float,
    right_bound: float,
    page_height: int,
) -> tuple[str, list[Word]]:
    """Walk the rows below a label and collect value words inside its column."""

    collected: list[Word] = []
    limit = anchor_row.top + page_height * 0.12
    for row in rows:
        if row.top <= anchor_row.top + 2:
            continue
        if row.top > limit:
            break
        if any(
            _is_label(word.text, NAME_LABELS) or _is_label(word.text, REGISTER_LABELS)
            for word in row.words
        ):
            if collected:
                break
            continue
        inside = [
            word
            for word in row.words
            if left_bound - 4 <= word.center_x <= right_bound
            and _clean_token(word.text) not in LABEL_NOISE
        ]
        if inside:
            collected.extend(inside)
            break
    if not collected:
        return "", []
    ordered = sorted(collected, key=lambda word: word.left)
    return " ".join(word.text for word in ordered), ordered


def _find_identity(pages: list[OcrPage], raw_text: str) -> tuple[Field, Field, Field, list[str]]:
    warnings: list[str] = []
    name = Field()
    register = Field()
    year = Field()

    anchor_rows: list[tuple[OcrPage, Row, Word, str]] = []
    rows_by_page: dict[int, list[Row]] = {}
    for page in pages:
        rows = visual_rows(page.words)
        rows_by_page[page.number] = rows
        for row in rows:
            for word in row.words:
                if _is_label(word.text, NAME_LABELS):
                    anchor_rows.append((page, row, word, "name"))
                if _is_label(word.text, REGISTER_LABELS):
                    anchor_rows.append((page, row, word, "register"))

    for page, row, word, kind in anchor_rows:
        other_labels = [
            other
            for other in row.words
            if other.left > word.left
            and (
                _is_label(other.text, NAME_LABELS)
                or _is_label(other.text, REGISTER_LABELS)
                or _clean_token(other.text) in {"examination", "board", "year"}
            )
        ]
        boundary = min((other.left for other in other_labels), default=page.width - 16)
        if kind == "name":
            if name.value:
                continue
            inline = [
                other
                for other in row.words
                if other.left > word.right + 2
                and other.left < boundary
                and _alpha_ratio(other) > 0.5
                and _clean_token(other.text) not in LABEL_NOISE
            ]
            text, words = _row_value(
                rows_by_page[page.number],
                word,
                row,
                left_bound=word.left - 12,
                right_bound=boundary,
                page_height=page.height,
            )
            if not text and inline:
                words = sorted(inline, key=lambda item: item.left)
                text = " ".join(item.text for item in words)
            if text and len(ALPHA.findall(text)) >= 2:
                name = Field(value=text, confidence=_confidence(words or [word]), page=page.number)
        else:
            if register.value:
                continue
            inline = [
                other
                for other in row.words
                if other.left > word.right + 2 and DIGIT.search(other.text)
            ]
            if inline:
                candidate = min(inline, key=lambda item: item.left)
                register = Field(
                    value=candidate.text.strip(".,:;"),
                    confidence=candidate.confidence,
                    page=page.number,
                )
                continue
            text, words = _row_value(
                rows_by_page[page.number],
                word,
                row,
                left_bound=word.left - 12,
                right_bound=page.width - 12,
                page_height=page.height,
            )
            if text:
                token = next((word for word in words if DIGIT.search(word.text)), None)
                if token is not None:
                    register = Field(
                        value=token.text.strip(".,:;"),
                        confidence=_confidence([token]),
                        page=page.number,
                    )

    # Regex fallbacks keep the pipeline useful on line-oriented statements that
    # defeat the geometric label pass.
    if not register.value:
        match = re.search(
            r"(?:REG(?:ISTER)?|ROLL|ENROL(?:L)?MENT)\s*(?:NO\.?|NUMBER|NUM|#)?\s*[:\-]?\s*"
            r"([A-Z0-9][A-Z0-9/\-]{3,})",
            raw_text,
            flags=re.IGNORECASE,
        )
        if match and sum(character.isdigit() for character in match.group(1)) >= 2:
            register = Field(value=match.group(1), confidence=55.0)
    if not register.value:
        token = re.search(r"\b[A-Z]{2,}[0-9]{2,}[A-Z0-9/\-]*\b", raw_text)
        if token:
            register = Field(value=token.group(0), confidence=50.0)

    if not name.value:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if re.search(r"\b(candidate|applicant|student name|name)\b", line, flags=re.IGNORECASE):
                cleaned = re.sub(
                    r"\b(candidate|applicant|student|name|register|reg|no\.?|number)\b",
                    " ",
                    line,
                    flags=re.IGNORECASE,
                ).strip(" :.-")
                if len(ALPHA.findall(cleaned)) >= 2:
                    name = Field(value=" ".join(cleaned.split()), confidence=58.0)
                    break
                if index + 1 < len(lines):
                    following = lines[index + 1]
                    if register.value:
                        following = following.replace(register.value, " ")
                    following = re.sub(r"\b(register|reg|no\.?)\b.*$", "", following, flags=re.IGNORECASE)
                    if len(ALPHA.findall(following)) >= 2:
                        name = Field(value=" ".join(following.split()), confidence=55.0)
                        break

    years = [int(match.group(0)) for match in YEAR.finditer(raw_text)]
    if years:
        # The exam session usually appears more than once; the modal year beats
        # picking the first four digits that happen to be printed.
        counts: dict[int, int] = {}
        for item in years:
            counts[item] = counts.get(item, 0) + 1
        chosen = max(counts, key=lambda item: (counts[item], -years.index(item)))
        year = Field(value=chosen, confidence=80.0)

    if not name.value:
        warnings.append("The candidate name could not be located on the mark sheet.")
    if not register.value:
        warnings.append("The register number could not be located on the mark sheet.")
    if not year.value:
        warnings.append("The examination year could not be located on the mark sheet.")
    return name, register, year, warnings


def extract_fields(pages: list[OcrPage]) -> Extraction:
    raw_text = "\n\n".join(page.text for page in pages).strip()
    name, register, year, warnings = _find_identity(pages, raw_text)
    subjects = extract_subjects(pages)
    if not subjects:
        warnings.append("No subject rows were recognised on the mark sheet.")
    low = [row for row in subjects if row.confidence < 60]
    if low:
        warnings.append(f"{len(low)} subject row(s) were read with low confidence.")
    return Extraction(
        pages=pages,
        name=name,
        register_number=register,
        exam_year=year,
        subjects=subjects,
        raw_text=raw_text,
        warnings=warnings,
    )
