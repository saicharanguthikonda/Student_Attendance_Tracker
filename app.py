from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.express as px
import streamlit as st

from data_manager import (
    DEFAULT_SUBJECTS,
    add_record,
    add_student,
    delete_student,
    export_backup,
    import_backup,
    load_records,
    load_students,
    save_records,
    update_student,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

st.set_page_config(
    page_title="Student Attendance Tracker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
div[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 12px;
    padding: 12px;
}
.small-note {opacity:.72;font-size:.86rem;}
</style>
""", unsafe_allow_html=True)


def init_state():
    defaults = {
        "students": load_students(DATA_DIR),
        "records": load_records(DATA_DIR),
        "page": "Dashboard",
        "edit_student_id": None,
        "flash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh():
    st.session_state.students = load_students(DATA_DIR)
    st.session_state.records = load_records(DATA_DIR)


def flash(message, level="success"):
    st.session_state.flash = (message, level)


def show_flash():
    item = st.session_state.get("flash")
    if not item:
        return
    message, level = item
    getattr(st, level)(message)
    st.session_state.flash = None


def attendance_df():
    students = pd.DataFrame(st.session_state.students)
    records = pd.DataFrame(st.session_state.records)
    if students.empty:
        return pd.DataFrame(columns=["student_id", "roll_no", "name", "class_name", "section", "subject", "date", "status"])

    students = students.rename(columns={"id": "student_id"})
    if records.empty:
        return pd.DataFrame(columns=["student_id", "roll_no", "name", "class_name", "section", "subject", "date", "status"])

    records = records.rename(columns={"student_id": "student_id"})
    merged = records.merge(
        students[["student_id", "roll_no", "name", "class_name", "section"]],
        on="student_id",
        how="left",
    )
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    return merged


def calculate_percentage(df):
    if df.empty:
        return 0.0
    return round((df["status"] == "Present").sum() / len(df) * 100, 2)


def dashboard():
    st.title("🎓 Student Attendance Tracker")
    st.caption("Local JSON attendance management with automated percentage calculations.")

    df = attendance_df()
    students_count = len(st.session_state.students)
    total_classes = len(df)
    present = int((df["status"] == "Present").sum()) if not df.empty else 0
    overall = round(present / total_classes * 100, 2) if total_classes else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", students_count)
    c2.metric("Attendance records", total_classes)
    c3.metric("Present", present)
    c4.metric("Overall attendance", f"{overall:.2f}%")

    if df.empty:
        st.info("No attendance records yet. Add students and mark attendance.")
        return

    left, right = st.columns(2)
    with left:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.pie(status_counts, names="status", values="count", hole=.45, title="Attendance status")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        daily = df.groupby(["date", "status"]).size().reset_index(name="count")
        fig = px.bar(daily, x="date", y="count", color="status", barmode="stack", title="Daily attendance")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Student attendance summary")
    summary = (
        df.groupby(["student_id", "roll_no", "name", "class_name", "section"])
        .agg(total_classes=("status", "size"), present=("status", lambda s: (s == "Present").sum()))
        .reset_index()
    )
    summary["absent"] = summary["total_classes"] - summary["present"]
    summary["percentage"] = (summary["present"] / summary["total_classes"] * 100).round(2)
    summary["status"] = summary["percentage"].apply(
        lambda x: "🔴 Critical" if x < 65 else ("🟠 Low" if x < 75 else ("🟢 Good" if x < 85 else "🔵 Excellent"))
    )
    st.dataframe(
        summary[["roll_no", "name", "class_name", "section", "total_classes", "present", "absent", "percentage", "status"]]
        .sort_values("percentage"),
        use_container_width=True,
        hide_index=True,
        column_config={"percentage": st.column_config.NumberColumn("Attendance %", format="%.2f%%")},
    )


def add_student_page():
    st.title("👨‍🎓 Student Registration")
    st.caption("Custom form for adding student profiles.")

    with st.form("student_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        roll = c1.text_input("Roll number *", placeholder="e.g. CSE001")
        name = c2.text_input("Student name *")
        class_name = c3.text_input("Class / Year *", placeholder="e.g. B.Tech 3rd Year")

        c4, c5 = st.columns(2)
        section = c4.text_input("Section", value="A")
        email = c5.text_input("Email (optional)")
        phone = st.text_input("Phone (optional)")
        submitted = st.form_submit_button("Add student", type="primary", use_container_width=True)

    if submitted:
        try:
            add_student(DATA_DIR, {
                "id": uuid4().hex,
                "roll_no": roll.strip(),
                "name": name.strip(),
                "class_name": class_name.strip(),
                "section": section.strip() or "A",
                "email": email.strip(),
                "phone": phone.strip(),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            })
            refresh()
            flash("Student added successfully.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except OSError as exc:
            st.error(f"Could not save student: {exc}")


def manage_students():
    st.title("👥 Manage Students")
    students = st.session_state.students

    if not students:
        st.info("No students registered.")
        return

    query = st.text_input("Search by roll number or name", placeholder="Type to search...")
    filtered = [
        s for s in students
        if not query.strip()
        or query.lower() in s["roll_no"].lower()
        or query.lower() in s["name"].lower()
    ]

    display = pd.DataFrame(filtered)
    if not display.empty:
        st.dataframe(
            display[["roll_no", "name", "class_name", "section", "email", "phone"]],
            use_container_width=True,
            hide_index=True,
        )

    choices = [s["id"] for s in filtered]
    labels = {s["id"]: f"{s['roll_no']} • {s['name']}" for s in filtered}
    if not choices:
        st.warning("No matching students.")
        return

    selected_id = st.selectbox("Select student", choices, format_func=lambda x: labels[x])
    selected = next(s for s in students if s["id"] == selected_id)

    c1, c2 = st.columns(2)
    if c1.button("✏️ Edit student", use_container_width=True):
        st.session_state.edit_student_id = selected_id
        st.rerun()
    if c2.button("🗑️ Delete student", use_container_width=True):
        st.session_state[f"delete_{selected_id}"] = True

    if st.session_state.get(f"delete_{selected_id}"):
        st.warning("Deleting a student also deletes that student's attendance records.")
        a, b = st.columns(2)
        if a.button("Confirm delete", type="primary", use_container_width=True):
            try:
                delete_student(DATA_DIR, selected_id)
                st.session_state[f"delete_{selected_id}"] = False
                st.session_state.edit_student_id = None
                refresh()
                flash("Student and related attendance records deleted.", "warning")
                st.rerun()
            except OSError as exc:
                st.error(f"Delete failed: {exc}")
        if b.button("Cancel", use_container_width=True):
            st.session_state[f"delete_{selected_id}"] = False
            st.rerun()

    if st.session_state.edit_student_id:
        student = next(
            (s for s in students if s["id"] == st.session_state.edit_student_id), None
        )
        if student:
            st.divider()
            st.subheader("Edit student")
            with st.form("edit_student_form"):
                roll = st.text_input("Roll number", value=student["roll_no"])
                name = st.text_input("Name", value=student["name"])
                class_name = st.text_input("Class / Year", value=student["class_name"])
                section = st.text_input("Section", value=student["section"])
                email = st.text_input("Email", value=student.get("email", ""))
                phone = st.text_input("Phone", value=student.get("phone", ""))
                save = st.form_submit_button("Save changes", type="primary")
            if save:
                try:
                    update_student(DATA_DIR, student["id"], {
                        "roll_no": roll.strip(),
                        "name": name.strip(),
                        "class_name": class_name.strip(),
                        "section": section.strip() or "A",
                        "email": email.strip(),
                        "phone": phone.strip(),
                    })
                    st.session_state.edit_student_id = None
                    refresh()
                    flash("Student updated successfully.")
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))


def mark_attendance():
    st.title("📝 Mark Attendance")
    students = st.session_state.students
    if not students:
        st.info("Register students before marking attendance.")
        return

    student_map = {s["id"]: s for s in students}
    selected_date = st.date_input("Attendance date", value=date.today(), max_value=date.today())
    subject = st.selectbox("Subject", DEFAULT_SUBJECTS)
    notes = st.text_input("Class note (optional)", placeholder="e.g. Unit 3 lecture")

    existing = {
        r["student_id"]: r["status"]
        for r in st.session_state.records
        if r["date"] == selected_date.isoformat() and r["subject"] == subject
    }

    st.subheader(f"Attendance for {selected_date.strftime('%d %b %Y')} • {subject}")
    if existing:
        st.info("Attendance already exists for this date and subject. Saving will update the selected records.")

    selected_status = {}
    cols = st.columns(2)
    for index, student in enumerate(sorted(students, key=lambda x: x["roll_no"].lower())):
        with cols[index % 2]:
            selected_status[student["id"]] = st.radio(
                f"{student['roll_no']} — {student['name']}",
                ["Present", "Absent"],
                index=0 if existing.get(student["id"], "Present") == "Present" else 1,
                horizontal=True,
                key=f"status_{selected_date}_{subject}_{student['id']}",
            )

    if st.button("💾 Save attendance", type="primary", use_container_width=True):
        try:
            for student_id, status in selected_status.items():
                add_record(DATA_DIR, {
                    "id": uuid4().hex,
                    "student_id": student_id,
                    "date": selected_date.isoformat(),
                    "subject": subject,
                    "status": status,
                    "notes": notes.strip(),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                })
            refresh()
            flash(f"Attendance saved for {len(selected_status)} students.")
            st.rerun()
        except (ValueError, OSError) as exc:
            st.error(str(exc))


def reports():
    st.title("📊 Reports & Analytics")
    df = attendance_df()
    if df.empty:
        st.info("No attendance data available.")
        return

    c1, c2, c3 = st.columns(3)
    classes = sorted(df["class_name"].dropna().unique())
    subjects = sorted(df["subject"].dropna().unique())
    selected_class = c1.selectbox("Class", ["All"] + classes)
    selected_subject = c2.selectbox("Subject", ["All"] + subjects)
    threshold = c3.slider("Minimum attendance target %", 50, 100, 75)

    filtered = df.copy()
    if selected_class != "All":
        filtered = filtered[filtered["class_name"] == selected_class]
    if selected_subject != "All":
        filtered = filtered[filtered["subject"] == selected_subject]

    if filtered.empty:
        st.warning("No records match the selected filters.")
        return

    summary = (
        filtered.groupby(["student_id", "roll_no", "name", "class_name", "section"])
        .agg(total_classes=("status", "size"), present=("status", lambda s: (s == "Present").sum()))
        .reset_index()
    )
    summary["absent"] = summary["total_classes"] - summary["present"]
    summary["attendance_percentage"] = (
        summary["present"] / summary["total_classes"] * 100
    ).round(2)
    summary["below_target"] = summary["attendance_percentage"] < threshold

    st.subheader("Individual attendance")
    st.dataframe(
        summary[[
            "roll_no", "name", "class_name", "section",
            "total_classes", "present", "absent",
            "attendance_percentage", "below_target"
        ]].sort_values("attendance_percentage"),
        use_container_width=True,
        hide_index=True,
        column_config={
            "attendance_percentage": st.column_config.NumberColumn("Attendance %", format="%.2f%%"),
            "below_target": st.column_config.CheckboxColumn("Below target"),
        },
    )

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            summary.sort_values("attendance_percentage"),
            x="name",
            y="attendance_percentage",
            hover_data=["roll_no", "total_classes", "present", "absent"],
            title="Attendance percentage by student",
        )
        fig.add_hline(y=threshold, line_dash="dash", annotation_text=f"Target {threshold}%")
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        subject_summary = (
            filtered.groupby("subject")
            .agg(classes=("status", "size"), present=("status", lambda s: (s == "Present").sum()))
            .reset_index()
        )
        subject_summary["percentage"] = (
            subject_summary["present"] / subject_summary["classes"] * 100
        ).round(2)
        fig = px.bar(subject_summary, x="subject", y="percentage", text="percentage", title="Subject-wise attendance")
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    csv = summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download attendance report (CSV)",
        csv,
        file_name=f"attendance_report_{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def general_tools():
    st.title("🛠️ General Tools")
    st.caption("Utilities for quick data operations, validation, backup and application maintenance.")

    df = attendance_df()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Registered students", len(st.session_state.students))
        c2.metric("Attendance records", len(df))
        c3.metric("Unique dates", df["date"].dt.date.nunique())

        st.subheader("Quick search")
        query = st.text_input("Search student", placeholder="Name or roll number")
        if query:
            result = df[
                df["name"].str.contains(query, case=False, na=False)
                | df["roll_no"].str.contains(query, case=False, na=False)
            ]
            st.dataframe(
                result[["roll_no", "name", "class_name", "subject", "date", "status"]],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.subheader("Backup and restore")
    backup = export_backup(DATA_DIR)
    st.download_button(
        "⬇️ Download complete JSON backup",
        backup,
        file_name=f"attendance_backup_{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded = st.file_uploader("Restore JSON backup", type=["json"])
    if uploaded and st.button("Restore backup", type="primary"):
        try:
            import_backup(DATA_DIR, uploaded.getvalue())
            refresh()
            flash("Backup restored successfully.")
            st.rerun()
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            st.error(f"Restore failed: {exc}")

    st.divider()
    st.subheader("Data maintenance")
    st.write("Export a backup before using destructive maintenance operations.")
    if st.button("Delete all attendance records", type="secondary"):
        st.session_state.confirm_clear_records = True
    if st.session_state.get("confirm_clear_records"):
        st.warning("This deletes attendance records but keeps student profiles.")
        a, b = st.columns(2)
        if a.button("Confirm clear", type="primary"):
            save_records(DATA_DIR, [])
            st.session_state.confirm_clear_records = False
            refresh()
            flash("All attendance records deleted.", "warning")
            st.rerun()
        if b.button("Cancel"):
            st.session_state.confirm_clear_records = False
            st.rerun()


def sidebar():
    st.sidebar.title("🎓 Attendance Tracker")
    pages = [
        "Dashboard",
        "Student Registration",
        "Manage Students",
        "Mark Attendance",
        "Reports & Analytics",
        "General Tools",
    ]
    selected = st.sidebar.radio("Navigation", pages, index=pages.index(st.session_state.page))
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.session_state.edit_student_id = None

    st.sidebar.divider()
    st.sidebar.caption("JSON storage • Custom forms • Automatic percentages")
    st.sidebar.info("Attendance target is configurable in Reports & Analytics.")


init_state()
sidebar()
show_flash()

page = st.session_state.page
if page == "Dashboard":
    dashboard()
elif page == "Student Registration":
    add_student_page()
elif page == "Manage Students":
    manage_students()
elif page == "Mark Attendance":
    mark_attendance()
elif page == "Reports & Analytics":
    reports()
elif page == "General Tools":
    general_tools()
