import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import engine, get_db, Base, SessionLocal
from app.models import Student
from app.scanner import verify_and_mark_lunch
from app.excel_import import parse_and_import_excel, generate_excel_export

# Initialize DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student Lunch QR Verification System", version="1.0.0")

# Setup static files & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def auto_seed_excel_on_startup():
    """
    If database is empty on startup, automatically parse and load default Excel file.
    """
    db = SessionLocal()
    try:
        count = db.query(Student).count()
        if count == 0:
            for filepath in ["sample_students_temp.xlsx", "sample_students_data.xlsx", "sample_students.xlsx"]:
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        result = parse_and_import_excel(db, f.read())
                        print(f"Auto-loaded Excel data from '{filepath}': {result['message']}")
                    break
    except Exception as e:
        print(f"Auto-seed warning: {e}")
    finally:
        db.close()


class ScanRequest(BaseModel):
    token: Optional[str] = None
    roll_number: Optional[str] = None


# --- Web Page Routes ---

@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/scanner")

@app.get("/scanner", response_class=HTMLResponse)
def scanner_page(request: Request):
    return templates.TemplateResponse(request=request, name="scanner.html")

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")


# --- API Endpoints ---

@app.post("/api/scan")
def scan_qr(payload: ScanRequest, db: Session = Depends(get_db)):
    """
    Scans student QR code containing Roll Number and updates database atomically.
    """
    scanned_value = (payload.roll_number or payload.token or "").strip()
    if not scanned_value:
        raise HTTPException(status_code=400, detail="Roll Number / Token is required.")
    
    result = verify_and_mark_lunch(db, scanned_value)
    return result


@app.get("/api/admin/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Returns real-time dashboard stats:
    TOTAL_STUDENTS, LUNCH_OPTED, LUNCH_USED, REMAINING
    """
    total = db.query(Student).count()
    opted = db.query(Student).filter(Student.lunch_opted == True).count()
    used = db.query(Student).filter(Student.lunch_opted == True, Student.lunch_used == True).count()
    remaining = opted - used

    return {
        "total": total,
        "opted": opted,
        "used": used,
        "remaining": remaining
    }


@app.get("/api/admin/students")
def get_students(search: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Returns list of students filtered optionally by search term (roll_number or name).
    """
    query = db.query(Student)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Student.roll_number.ilike(term)) | (Student.name.ilike(term))
        )
    
    students = query.order_by(Student.roll_number.asc()).all()
    return [s.to_dict() for s in students]


@app.post("/api/admin/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    replace_existing: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Upload Excel file (.xlsx) and import student data.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel (.xlsx) file.")

    contents = await file.read()
    result = parse_and_import_excel(db, contents, replace_all=replace_existing)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result


@app.post("/api/admin/load-default-excel")
def load_default_excel(replace_existing: bool = Query(True), db: Session = Depends(get_db)):
    """
    Loads pre-placed Excel file into database, replacing old records by default.
    """
    for filepath in ["sample_students_temp.xlsx", "sample_students_data.xlsx", "sample_students.xlsx"]:
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                result = parse_and_import_excel(db, f.read(), replace_all=replace_existing)
                return result
    raise HTTPException(status_code=404, detail="No pre-placed Excel file found on server.")


@app.post("/api/admin/clear-all")
def clear_all_students(db: Session = Depends(get_db)):
    """
    Clears all student records from database.
    """
    deleted = db.query(Student).delete()
    db.commit()
    return {"success": True, "message": f"Cleared {deleted} student records from database."}


@app.post("/api/admin/reset/{student_id}")
def reset_student_lunch(student_id: int, db: Session = Depends(get_db)):
    """
    Resets an accidentally used student lunch status back to unused.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    
    student.lunch_used = False
    student.used_at = None
    db.commit()

    return {"success": True, "message": f"Reset lunch status for {student.name} ({student.roll_number})."}


@app.get("/api/admin/export")
def export_excel(db: Session = Depends(get_db)):
    """
    Exports final student data to downloadable Excel file.
    """
    excel_stream = generate_excel_export(db)
    filename = "student_lunch_report.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
