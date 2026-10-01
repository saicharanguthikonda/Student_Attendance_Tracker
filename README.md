# 🎓 Student Attendance Tracker

A complete Student Attendance Tracker built using Python, Streamlit and local JSON files.

## Major requirements

- Custom Streamlit forms
- Structured JSON data handling
- Automated attendance percentage calculations
- No traditional database
- Local JSON persistence
- Interactive Plotly charts
- Streamlit Community Cloud deployment ready

## Features

### Student management
- Register students
- Unique roll-number validation
- Search students
- Edit student profiles
- Delete students
- Deleting a student also removes related attendance records

### Attendance
- Select attendance date
- Select subject
- Mark Present/Absent for all students
- Existing date + subject + student records are updated rather than duplicated
- Optional class notes

### Automatic calculations
For each student:

Attendance % = Present Classes / Total Classes × 100

The dashboard also shows overall attendance.

### Reports
- Filter by class
- Filter by subject
- Select attendance target
- Individual attendance percentage
- Present/absent totals
- Students below target
- Subject-wise attendance
- Interactive charts
- CSV report download

### General Tools
- Quick student search
- Complete JSON backup
- JSON restore
- Data summary
- Delete all attendance records with confirmation

## Structure

```text
student_attendance_tracker/
├── app.py
├── data_manager.py
├── requirements.txt
├── README.md
├── test_app.py
├── .gitignore
├── .streamlit/
│   └── config.toml
└── data/
    ├── students.json
    └── attendance.json
```

## Run locally

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install:

```bash
pip install -r requirements.txt
```

Run:

```bash
streamlit run app.py
```

## Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload the complete project.
3. Sign in to Streamlit Community Cloud.
4. Connect your GitHub account.
5. Create a new app.
6. Select your repository and branch.
7. Set the main file to `app.py`.
8. Deploy.

`requirements.txt` is in the project root, so the required Python packages can be installed during deployment.

## JSON storage warning

This project intentionally uses local JSON instead of a database. This is suitable for local use, academic projects, prototypes and demonstrations.

On a hosted environment, local filesystem changes should not be considered durable cloud storage. A restart, redeployment or environment replacement may remove changes made to JSON files.

Use **General Tools → Download complete JSON backup** regularly.

For a production multi-user attendance system, use durable storage such as a managed database or persistent storage service.

## Data model

### students.json

```json
{
  "id": "unique-id",
  "roll_no": "CSE001",
  "name": "Student Name",
  "class_name": "B.Tech 3rd Year",
  "section": "A",
  "email": "student@example.com",
  "phone": "9999999999",
  "created_at": "2026-10-01T09:00:00"
}
```

### attendance.json

```json
{
  "id": "unique-id",
  "student_id": "student-id",
  "date": "2026-10-01",
  "subject": "Python",
  "status": "Present",
  "notes": "Unit 3 lecture",
  "created_at": "2026-10-01T09:30:00"
}
```

## Architecture

```text
             Streamlit UI
                  │
          ┌───────┴────────┐
          │                │
   Session State       User Forms
          │                │
          └───────┬────────┘
                  │
           data_manager.py
                  │
       ┌──────────┴──────────┐
       │                     │
 students.json         attendance.json
```

## Testing

`test_app.py` performs smoke tests for:

- Student creation
- Duplicate roll-number protection
- Student update
- Attendance creation
- Attendance upsert behavior
- Backup creation
- Backup restoration
- Student deletion and related-record deletion

Run:

```bash
python test_app.py
```
