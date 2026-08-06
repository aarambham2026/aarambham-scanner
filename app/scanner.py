from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Student

def verify_and_mark_lunch(db: Session, roll_number: str) -> dict:
    """
    Verifies scanned Roll Number with atomic UPDATE to prevent race conditions across multiple scanners.

    Statuses returned:
    - INVALID_QR: Roll Number does not exist in DB
    - NOT_ELIGIBLE: Student exists but lunch_opted = False
    - ALREADY_USED: Student lunch was already scanned previously
    - ALLOWED: Lunch claimed successfully
    """
    clean_roll = roll_number.strip()
    if not clean_roll:
        return {"status": "INVALID_QR", "message": "Empty QR code."}

    # Step 1: Check if student exists by Roll Number
    student = db.query(Student).filter(Student.roll_number == clean_roll).first()
    if not student:
        return {
            "status": "INVALID_QR",
            "message": f"Invalid QR code. Roll Number '{clean_roll}' not found."
        }

    # Step 2: Check if student opted for lunch
    if not student.lunch_opted:
        return {
            "status": "NOT_ELIGIBLE",
            "message": "Not eligible for lunch.",
            "student": {
                "name": student.name,
                "roll_number": student.roll_number
            }
        }

    # Step 3: CRITICAL ATOMIC UPDATE (using Roll Number)
    now = datetime.now()
    dialect = db.bind.dialect.name if db.bind else "postgresql"

    if dialect == "postgresql":
        raw_sql = text("""
            UPDATE registrations
            SET lunch_used = TRUE,
                used_at = CURRENT_TIMESTAMP
            WHERE roll_number = :roll_number
              AND lunch_opted = TRUE
              AND lunch_used = FALSE
            RETURNING roll_number, name, used_at;
        """)
        result = db.execute(raw_sql, {"roll_number": clean_roll})
        row = result.fetchone()
        db.commit()

        if row:
            used_at_val = row.used_at
            if isinstance(used_at_val, datetime):
                used_time_str = used_at_val.strftime("%d %b %Y, %I:%M:%S %p")
            else:
                used_time_str = str(used_at_val) if used_at_val else now.strftime("%d %b %Y, %I:%M:%S %p")
            return {
                "status": "ALLOWED",
                "message": "ENTRY ALLOWED",
                "student": {
                    "name": row.name,
                    "roll_number": row.roll_number,
                    "used_at": used_time_str
                }
            }
    else:
        # Cross-database atomic update
        updated_rows = db.query(Student).filter(
            Student.roll_number == clean_roll,
            Student.lunch_opted == True,
            Student.lunch_used == False
        ).update(
            {Student.lunch_used: True, Student.used_at: now},
            synchronize_session=False
        )
        db.commit()

        if updated_rows > 0:
            return {
                "status": "ALLOWED",
                "message": "ENTRY ALLOWED",
                "student": {
                    "name": student.name,
                    "roll_number": student.roll_number,
                    "used_at": now.strftime("%d %b %Y, %I:%M:%S %p")
                }
            }

    # If 0 rows updated, it was ALREADY USED!
    db.refresh(student)
    used_at_val = student.used_at
    if isinstance(used_at_val, datetime):
        used_time_str = used_at_val.strftime("%d %b %Y, %I:%M:%S %p")
    elif used_at_val:
        used_time_str = str(used_at_val)
    else:
        used_time_str = "Previously used"

    return {
        "status": "ALREADY_USED",
        "message": "Lunch already claimed.",
        "student": {
            "name": student.name,
            "roll_number": student.roll_number,
            "used_at": used_time_str
        }
    }
