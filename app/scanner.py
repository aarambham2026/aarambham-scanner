from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Student

def verify_and_mark_event_entry(db: Session, roll_number: str) -> dict:
    """
    Verifies scanned Roll Number for Aarambham event registration with atomic UPDATE to prevent race conditions across multiple scanners.

    Statuses returned:
    - NOT_REGISTERED: Roll Number does not exist in DB or registered = False
    - ALLOWED: Registered student checked in successfully
    - ALREADY_CHECKED_IN: Student was already checked in previously
    """
    clean_roll = roll_number.strip()
    if not clean_roll:
        return {"status": "INVALID_QR", "message": "Empty QR code."}

    # Step 1: Check if student exists by Roll Number
    student = db.query(Student).filter(Student.roll_number == clean_roll).first()
    if not student or not student.registered:
        return {
            "status": "NOT_REGISTERED",
            "message": f"Student not registered for Aarambham event. Roll Number '{clean_roll}' not found.",
            "roll_number": clean_roll
        }

    # Step 2: CRITICAL ATOMIC UPDATE for Check-In
    now = datetime.now()
    dialect = db.bind.dialect.name if db.bind else "postgresql"

    if dialect == "postgresql":
        raw_sql = text("""
            UPDATE registrations
            SET checked_in = TRUE,
                checked_in_at = CURRENT_TIMESTAMP
            WHERE roll_number = :roll_number
              AND registered = TRUE
              AND checked_in = FALSE
            RETURNING roll_number, name, checked_in_at;
        """)
        result = db.execute(raw_sql, {"roll_number": clean_roll})
        row = result.fetchone()
        db.commit()

        if row:
            checked_in_val = row.checked_in_at
            if isinstance(checked_in_val, datetime):
                checked_in_time_str = checked_in_val.strftime("%d %b %Y, %I:%M:%S %p")
            else:
                checked_in_time_str = str(checked_in_val) if checked_in_val else now.strftime("%d %b %Y, %I:%M:%S %p")
            return {
                "status": "ALLOWED",
                "message": "REGISTERED — ENTRY ALLOWED",
                "student": {
                    "name": row.name,
                    "roll_number": row.roll_number,
                    "checked_in_at": checked_in_time_str
                }
            }
    else:
        # Cross-database atomic update
        updated_rows = db.query(Student).filter(
            Student.roll_number == clean_roll,
            Student.registered == True,
            Student.checked_in == False
        ).update(
            {Student.checked_in: True, Student.checked_in_at: now},
            synchronize_session=False
        )
        db.commit()

        if updated_rows > 0:
            return {
                "status": "ALLOWED",
                "message": "REGISTERED — ENTRY ALLOWED",
                "student": {
                    "name": student.name,
                    "roll_number": student.roll_number,
                    "checked_in_at": now.strftime("%d %b %Y, %I:%M:%S %p")
                }
            }

    # If 0 rows updated, student was ALREADY CHECKED IN!
    db.refresh(student)
    checked_in_val = student.checked_in_at
    if isinstance(checked_in_val, datetime):
        checked_in_time_str = checked_in_val.strftime("%d %b %Y, %I:%M:%S %p")
    elif checked_in_val:
        checked_in_time_str = str(checked_in_val)
    else:
        checked_in_time_str = "Previously checked in"

    return {
        "status": "ALREADY_CHECKED_IN",
        "message": "Student already checked in.",
        "student": {
            "name": student.name,
            "roll_number": student.roll_number,
            "checked_in_at": checked_in_time_str
        }
    }
