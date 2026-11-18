from __future__ import annotations

from copy import deepcopy

APPLICATION = {
    "applicant_name": "Test Student",
    "date_of_birth": "2008-04-18",
    "father_name": "Ravi Student",
    "mother_name": "Lakshmi Student",
    "phone": "+91 98765 43210",
    "address": "12, Gandhi Street, Chennai 600028",
    "is_orphan": False,
    "is_first_graduate": True,
    "class_10": {
        "register_number": "REG2024A014",
        "exam_year": 2024,
        "board": "State Board",
        "marks": [
            {"subject": "Mathematics", "marks_obtained": 94, "max_marks": 100},
            {"subject": "Science", "marks_obtained": 91, "max_marks": 100},
            {"subject": "Social Science", "marks_obtained": 88, "max_marks": 100},
            {"subject": "English", "marks_obtained": 90, "max_marks": 100},
            {"subject": "Tamil", "marks_obtained": 86, "max_marks": 100},
        ],
    },
    "class_11": {
        "register_number": "REG2025A014",
        "exam_year": 2025,
        "board": "State Board",
        "marks": [
            {"subject": "Mathematics", "marks_obtained": 88, "max_marks": 100},
            {"subject": "English", "marks_obtained": 90, "max_marks": 100},
            {"subject": "Physics", "marks_obtained": 85, "max_marks": 100},
            {"subject": "Chemistry", "marks_obtained": 84, "max_marks": 100},
            {"subject": "Computer Science", "marks_obtained": 92, "max_marks": 100},
        ],
    },
    "class_12": {
        "register_number": "reg2026a014",
        "exam_year": 2026,
        "board": "State Board",
        "marks": [
            {"subject": "Mathematics", "marks_obtained": 85, "max_marks": 100},
            {"subject": "English", "marks_obtained": 92, "max_marks": 100},
            {"subject": "Physics", "marks_obtained": 81, "max_marks": 100},
            {"subject": "Chemistry", "marks_obtained": 79, "max_marks": 100},
        ],
    },
}


def application_payload(**overrides) -> dict:
    data = deepcopy(APPLICATION)
    data.update(overrides)
    return data
