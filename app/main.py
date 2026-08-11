import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import engine, get_db, Base, SessionLocal
from app.models import Student
from app.scanner import verify_and_mark_event_entry
from app.excel_import import parse_and_import_excel, generate_excel_export
from app.auth import (
    verify_credentials,
    generate_session_token,
    get_current_admin,
    get_current_user,
    get_current_user_from_request
)

# Initialize DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Aarambham Event Verification System", version="1.0.0")

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
            for filepath in ["sample_students.xlsx", "sample_students_data.xlsx", "sample_students_temp.xlsx"]:
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


class LoginRequest(BaseModel):
    username: str
    password: str


# --- Web Page Routes ---

@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/scanner")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/scanner", response_class=HTMLResponse)
def scanner_page(request: Request):
    return templates.TemplateResponse(request=request, name="scanner.html")

@app.get("/guest", response_class=HTMLResponse)
def guest_page(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="guest.html")

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    user = get_current_user_from_request(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="admin.html")


# --- Authentication API Endpoints ---

@app.post("/api/login")
def login_endpoint(payload: LoginRequest, response: Response):
    user = verify_credentials(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    token = generate_session_token(user["username"], user["role"])
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )

    redirect_target = "/admin" if user["role"] == "admin" else "/guest"
    return {
        "success": True,
        "role": user["role"],
        "message": f"Successfully logged in as {user['role'].title()}.",
        "redirect": redirect_target
    }


@app.post("/api/logout")
def logout_endpoint(response: Response):
    response.delete_cookie("session_token")
    return {"success": True, "message": "Logged out successfully."}


# --- Gate Scanner API Endpoint ---

@app.post("/api/scan")
def scan_qr(payload: ScanRequest, db: Session = Depends(get_db)):
    """
    Scans student QR code containing Roll Number and verifies Aarambham event registration.
    """
    scanned_value = (payload.roll_number or payload.token or "").strip()
    if not scanned_value:
        raise HTTPException(status_code=400, detail="Roll Number / Token is required.")
    
    result = verify_and_mark_event_entry(db, scanned_value)
    return result


# --- Guest API Endpoints (Read-Only) ---

@app.get("/api/guest/stats")
def get_guest_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Returns real-time event entry stats for Guest View.
    """
    total = db.query(Student).count()
    registered = db.query(Student).filter(Student.registered == True).count()
    checked_in = db.query(Student).filter(Student.registered == True, Student.checked_in == True).count()
    pending = registered - checked_in

    return {
        "total": total,
        "registered": registered,
        "checked_in": checked_in,
        "pending": pending
    }


@app.get("/api/guest/students")
def get_guest_students(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Returns registered student records for Guest View with optional status filter.
    status_filter values: 'all', 'registered', 'checked_in', 'pending'
    """
    query = db.query(Student)

    if status_filter == "registered":
        query = query.filter(Student.registered == True)
    elif status_filter == "checked_in":
        query = query.filter(Student.registered == True, Student.checked_in == True)
    elif status_filter == "pending":
        query = query.filter(Student.registered == True, Student.checked_in == False)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Student.roll_number.ilike(term)) | (Student.name.ilike(term))
        )
    
    students = query.order_by(Student.checked_in.desc(), Student.roll_number.asc()).all()
    return [s.to_dict() for s in students]


# --- Admin API Endpoints (Requires Admin Role) ---

@app.get("/api/admin/stats")
def get_stats(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Returns real-time dashboard stats for Aarambham event administration.
    """
    total = db.query(Student).count()
    registered = db.query(Student).filter(Student.registered == True).count()
    checked_in = db.query(Student).filter(Student.registered == True, Student.checked_in == True).count()
    pending = registered - checked_in

    return {
        "total": total,
        "registered": registered,
        "checked_in": checked_in,
        "pending": pending
    }


@app.get("/api/admin/students")
def get_students(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Returns list of all registered students for Admin view with status filtering.
    """
    query = db.query(Student)

    if status_filter == "registered":
        query = query.filter(Student.registered == True)
    elif status_filter == "checked_in":
        query = query.filter(Student.registered == True, Student.checked_in == True)
    elif status_filter == "pending":
        query = query.filter(Student.registered == True, Student.checked_in == False)

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
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
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


@app.post("/api/admin/clear-all")
def clear_all_students(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Clears all student records from database.
    """
    deleted = db.query(Student).delete()
    db.commit()
    return {"success": True, "message": f"Cleared {deleted} student records from database."}


@app.post("/api/admin/reset/{student_id}")
def reset_student_checkin(
    student_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Resets an accidentally checked-in student back to pending check-in.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    
    student.checked_in = False
    student.checked_in_at = None
    db.commit()

    return {"success": True, "message": f"Reset check-in status for {student.name} ({student.roll_number})."}


@app.post("/api/admin/reset-all")
def reset_all_checkins(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Resets check-in status for ALL students back to pending check-in.
    """
    updated = db.query(Student).filter(Student.checked_in == True).update(
        {Student.checked_in: False, Student.checked_in_at: None},
        synchronize_session=False
    )
    db.commit()
    return {"success": True, "message": f"Successfully reset check-in status for {updated} students."}


@app.get("/api/admin/export")
def export_excel(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """
    Exports final Aarambham student registration & check-in data to downloadable Excel file.
    """
    excel_stream = generate_excel_export(db)
    filename = "aarambham_registration_report.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
