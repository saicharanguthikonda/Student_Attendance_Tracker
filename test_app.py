from pathlib import Path
import tempfile

from data_manager import (
    add_record,
    add_student,
    delete_student,
    export_backup,
    import_backup,
    load_records,
    load_students,
    update_student,
)


def run():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        student = {
            "id": "student-1",
            "roll_no": "CSE001",
            "name": "Test Student",
            "class_name": "B.Tech 3rd Year",
            "section": "A",
            "email": "",
            "phone": "",
        }
        add_student(root, student)
        assert len(load_students(root)) == 1

        try:
            add_student(root, {**student, "id": "student-2"})
            raise AssertionError("Duplicate roll number was accepted.")
        except ValueError:
            pass

        assert update_student(root, "student-1", {"name": "Updated Student"})
        assert load_students(root)[0]["name"] == "Updated Student"

        record = {
            "id": "record-1",
            "student_id": "student-1",
            "date": "2026-10-01",
            "subject": "Python",
            "status": "Present",
            "notes": "",
        }
        add_record(root, record)
        assert len(load_records(root)) == 1

        # Same student/date/subject should update, not duplicate.
        add_record(root, {**record, "id": "record-2", "status": "Absent"})
        assert len(load_records(root)) == 1
        assert load_records(root)[0]["status"] == "Absent"

        backup = export_backup(root)
        assert b'"students"' in backup
        assert b'"attendance"' in backup

        delete_student(root, "student-1")
        assert load_students(root) == []
        assert load_records(root) == []

        import_backup(root, backup)
        assert len(load_students(root)) == 1
        assert len(load_records(root)) == 1

    print("All attendance data-layer smoke tests passed.")


if __name__ == "__main__":
    run()
