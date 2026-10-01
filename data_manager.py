from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_SUBJECTS = [
    "Python",
    "Java",
    "DBMS",
    "Operating Systems",
    "Data Structures",
    "Computer Networks",
    "Mathematics",
    "Other",
]


def paths(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "students.json", data_dir / "attendance.json"


def atomic_write(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)


def read_json(path: Path, default):
    if not path.exists():
        atomic_write(path, default)
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        corrupt = path.with_suffix(path.suffix + ".corrupt")
        try:
            path.replace(corrupt)
        except OSError:
            pass
        atomic_write(path, default)
        return default


def load_students(data_dir: Path):
    student_path, _ = paths(data_dir)
    data = read_json(student_path, [])
    if not isinstance(data, list):
        raise ValueError("students.json must contain a JSON array.")
    return data


def save_students(data_dir: Path, students):
    student_path, _ = paths(data_dir)
    atomic_write(student_path, students)


def load_records(data_dir: Path):
    _, attendance_path = paths(data_dir)
    data = read_json(attendance_path, [])
    if not isinstance(data, list):
        raise ValueError("attendance.json must contain a JSON array.")
    return data


def save_records(data_dir: Path, records):
    _, attendance_path = paths(data_dir)
    atomic_write(attendance_path, records)


def validate_student(student):
    required = ["id", "roll_no", "name", "class_name", "section"]
    missing = [x for x in required if not str(student.get(x, "")).strip()]
    if missing:
        raise ValueError(f"Required student fields missing: {', '.join(missing)}")


def validate_record(record):
    required = ["id", "student_id", "date", "subject", "status"]
    missing = [x for x in required if not str(record.get(x, "")).strip()]
    if missing:
        raise ValueError(f"Required attendance fields missing: {', '.join(missing)}")
    if record["status"] not in {"Present", "Absent"}:
        raise ValueError("Attendance status must be Present or Absent.")
    try:
        datetime.fromisoformat(record["date"])
    except ValueError as exc:
        raise ValueError("Invalid attendance date.") from exc


def add_student(data_dir: Path, student):
    validate_student(student)
    students = load_students(data_dir)
    roll = student["roll_no"].strip().lower()
    if any(s["roll_no"].strip().lower() == roll for s in students):
        raise ValueError("Roll number already exists.")
    students.append(student)
    save_students(data_dir, students)


def update_student(data_dir: Path, student_id, changes):
    students = load_students(data_dir)
    for i, student in enumerate(students):
        if student["id"] == student_id:
            updated = {**student, **changes, "id": student_id}
            validate_student(updated)
            roll = updated["roll_no"].strip().lower()
            if any(s["id"] != student_id and s["roll_no"].strip().lower() == roll for s in students):
                raise ValueError("Another student already uses this roll number.")
            students[i] = updated
            save_students(data_dir, students)
            return True
    return False


def delete_student(data_dir: Path, student_id):
    students = load_students(data_dir)
    records = load_records(data_dir)
    new_students = [s for s in students if s["id"] != student_id]
    new_records = [r for r in records if r["student_id"] != student_id]
    if len(new_students) == len(students):
        return False
    save_students(data_dir, new_students)
    save_records(data_dir, new_records)
    return True


def add_record(data_dir: Path, record):
    validate_record(record)
    students = load_students(data_dir)
    if not any(s["id"] == record["student_id"] for s in students):
        raise ValueError("Student does not exist.")

    records = load_records(data_dir)

    # Upsert: one attendance status per student/date/subject.
    existing_index = next(
        (
            i for i, r in enumerate(records)
            if r["student_id"] == record["student_id"]
            and r["date"] == record["date"]
            and r["subject"] == record["subject"]
        ),
        None,
    )

    if existing_index is None:
        records.append(record)
    else:
        old = records[existing_index]
        records[existing_index] = {**old, **record, "id": old["id"]}

    save_records(data_dir, records)


def export_backup(data_dir: Path) -> bytes:
    payload = {
        "format": "student-attendance-tracker",
        "version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "students": load_students(data_dir),
        "attendance": load_records(data_dir),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def import_backup(data_dir: Path, raw: bytes):
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Backup must be a JSON object.")

    students = payload.get("students")
    records = payload.get("attendance")
    if not isinstance(students, list) or not isinstance(records, list):
        raise ValueError("Backup must contain students and attendance arrays.")

    seen_rolls = set()
    student_ids = set()
    for student in students:
        validate_student(student)
        roll = student["roll_no"].strip().lower()
        if roll in seen_rolls:
            raise ValueError(f"Duplicate roll number in backup: {student['roll_no']}")
        seen_rolls.add(roll)
        student_ids.add(student["id"])

    for record in records:
        validate_record(record)
        if record["student_id"] not in student_ids:
            raise ValueError("Backup contains attendance for an unknown student.")

    save_students(data_dir, students)
    save_records(data_dir, records)
