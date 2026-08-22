import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from sqlalchemy.orm import Session
from app.models import Student

def parse_and_import_excel(db: Session, file_bytes: bytes, replace_all: bool = False) -> dict:
    """
    Parses uploaded Excel file and upserts/replaces students in registrations table.
    Expected columns: Roll No (or Roll Number), Name, Registered (optional, YES/NO/True/False)
    """
    if replace_all:
        db.query(Student).delete()
        db.commit()

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheet = wb.active

    headers = []
    for cell in sheet[1]:
        headers.append(str(cell.value or "").strip().lower())

    col_map = {}
    for idx, h in enumerate(headers):
        if h in ["roll no", "roll number", "rollno", "roll_number", "roll"]:
            col_map["roll_number"] = idx
        elif h in ["name", "student name", "student_name"]:
            col_map["name"] = idx
        elif h in ["registered", "registration", "is_registered", "lunch opted", "lunch_opted", "opted"]:
            col_map["registered"] = idx

    required_cols = ["roll_number", "name"]
    missing = [c for c in required_cols if c not in col_map]
    if missing:
        return {
            "success": False,
            "message": f"Missing required columns in Excel: {', '.join(missing)}. Found: {headers}"
        }

    has_registered_col = "registered" in col_map

    added = 0
    updated = 0
    errors = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue

        try:
            roll = str(row[col_map["roll_number"]] or "").strip()
            name = str(row[col_map["name"]] or "").strip()

            if not roll or not name:
                errors += 1
                continue

            registered = True
            if has_registered_col and row[col_map["registered"]] is not None:
                val = str(row[col_map["registered"]]).strip().upper()
                registered = val in ["YES", "Y", "TRUE", "1", "REGISTERED"]

            existing = db.query(Student).filter(Student.roll_number == roll).first()

            if existing:
                existing.name = name
                existing.token = roll
                existing.registered = registered
                updated += 1
            else:
                student = Student(
                    roll_number=roll,
                    name=name,
                    token=roll,
                    registered=registered,
                    entry_time=None,
                    exit_time=None
                )
                db.add(student)
                added += 1

        except Exception:
            errors += 1

    db.commit()
    return {
        "success": True,
        "added": added,
        "updated": updated,
        "errors": errors,
        "message": f"Import complete! Added: {added}, Updated: {updated}, Errors/Skipped: {errors}"
    }


def generate_excel_export(db: Session) -> io.BytesIO:
    """
    Exports all student registrations and attendance data to an Excel workbook (.xlsx).
    """
    students = db.query(Student).order_by(Student.roll_number.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Aarambham Attendance Report"

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center")

    headers = ["Roll No", "Name", "Registration Status", "Entry Time", "Exit Time", "Status"]
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    from app.models import parse_and_format_ist

    for s in students:
        entry_str = parse_and_format_ist(s.entry_time) or "—"
        exit_str = parse_and_format_ist(s.exit_time) or "—"
        row = [
            s.roll_number,
            s.name,
            "REGISTERED" if s.registered else "NOT REGISTERED",
            entry_str,
            exit_str,
            s.status
        ]
        ws.append(row)

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
