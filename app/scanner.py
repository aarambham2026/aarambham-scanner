from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Student, parse_and_format_ist, IST

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

    # Step 2: CRITICAL ATOMIC UPDATE for Check-In (IST)
    now_ist = datetime.now(IST)
    dialect = db.bind.dialect.name if db.bind else "postgresql"

    if dialect == "postgresql":
        raw_sql = text("""
            UPDATE registrations
            SET checked_in = TRUE,
                checked_in_at = :now_ist
            WHERE roll_number = :roll_number
              AND registered = TRUE
              AND checked_in = FALSE
            RETURNING roll_number, name, checked_in_at;
        """)
        result = db.execute(raw_sql, {"roll_number": clean_roll, "now_ist": now_ist})
        row = result.fetchone()
        db.commit()

        if row:
            return {
                "status": "ALLOWED",
                "message": "REGISTERED — ENTRY ALLOWED",
                "student": {
                    "name": row.name,
                    "roll_number": row.roll_number,
                    "checked_in_at": parse_and_format_ist(row.checked_in_at) or now_ist.strftime("%d %b %Y, %I:%M:%S %p IST")
                }
            }
    else:
        # Cross-database atomic update
        updated_rows = db.query(Student).filter(
            Student.roll_number == clean_roll,
            Student.registered == True,
            Student.checked_in == False
        ).update(
            {Student.checked_in: True, Student.checked_in_at: now_ist},
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
                    "checked_in_at": now_ist.strftime("%d %b %Y, %I:%M:%S %p IST")
                }
            }

    # If 0 rows updated, student was ALREADY CHECKED IN!
    db.refresh(student)

    return {
        "status": "ALREADY_CHECKED_IN",
        "message": "Student already checked in.",
        "student": {
            "name": student.name,
            "roll_number": student.roll_number,
            "checked_in_at": parse_and_format_ist(student.checked_in_at) or "Previously checked in"
        }
    }
