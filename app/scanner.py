from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models import Student, parse_and_format_ist, IST

def verify_and_mark_event_entry(db: Session, roll_number: str) -> dict:
    """
    Verifies scanned Roll Number for Aarambham event entry and exit tracking with atomic UPDATE transitions.

    Workflow:
    - First scan (entry_time IS NULL, exit_time IS NULL): Records entry_time -> status 'entry_recorded'
    - Second scan (entry_time IS NOT NULL, exit_time IS NULL): Records exit_time -> status 'exit_recorded'
    - Subsequent scan (entry_time IS NOT NULL, exit_time IS NOT NULL): Returns status 'already_exited' without overwriting
    - Unregistered: Returns status 'not_registered'
    """
    clean_roll = roll_number.strip()
    if not clean_roll:
        return {
            "status": "invalid_qr",
            "message": "Empty QR code.",
            "name": None,
            "roll_no": "",
            "roll_number": "",
            "entry_time": None,
            "exit_time": None,
            "student": None
        }

    # Step 1: Check if student exists by Roll Number
    student = db.query(Student).filter(Student.roll_number == clean_roll).first()
    
    if not student:
        return {
            "status": "not_registered",
            "message": "NOT REGISTERED",
            "roll_no": clean_roll,
            "roll_number": clean_roll,
            "paid": "NO",
            "entry_time": None,
            "exit_time": None,
            "student": None
        }

    if not student.registered:
        return {
            "status": "unpaid",
            "message": "UNPAID / NOT ELIGIBLE",
            "roll_no": clean_roll,
            "roll_number": clean_roll,
            "paid": "NO",
            "entry_time": None,
            "exit_time": None,
            "student": student.to_dict()
        }

    now_ist = datetime.now(IST)
    dialect = db.bind.dialect.name if db.bind else "sqlite"

    # Step 2: ATOMIC ENTRY TRANSITION (entry_time IS NULL AND exit_time IS NULL)
    if dialect == "postgresql":
        raw_sql_entry = text("""
            UPDATE registrations
            SET entry_time = :now_ist
            WHERE roll_number = :roll_number
              AND registered = TRUE
              AND entry_time IS NULL
              AND exit_time IS NULL
            RETURNING roll_number, name, entry_time, exit_time;
        """)
        res = db.execute(raw_sql_entry, {"roll_number": clean_roll, "now_ist": now_ist})
        row_entry = res.fetchone()
        db.commit()

        if row_entry:
            formatted_entry = parse_and_format_ist(row_entry.entry_time, time_only=True) or now_ist.strftime("%I:%M:%S %p")
            return {
                "status": "entry_recorded",
                "name": row_entry.name,
                "roll_no": row_entry.roll_number,
                "roll_number": row_entry.roll_number,
                "paid": "YES",
                "entry_time": formatted_entry,
                "exit_time": None,
                "message": "ENTRY RECORDED",
                "student": {
                    "roll_number": row_entry.roll_number,
                    "roll_no": row_entry.roll_number,
                    "name": row_entry.name,
                    "paid": "YES",
                    "entry_time": formatted_entry,
                    "exit_time": None,
                    "status": "INSIDE"
                }
            }
    else:
        updated_entry = db.query(Student).filter(
            Student.roll_number == clean_roll,
            Student.registered == True,
            Student.entry_time == None,
            Student.exit_time == None
        ).update(
            {Student.entry_time: now_ist},
            synchronize_session=False
        )
        db.commit()

        if updated_entry > 0:
            db.refresh(student)
            formatted_entry = parse_and_format_ist(student.entry_time, time_only=True) or now_ist.strftime("%I:%M:%S %p")
            return {
                "status": "entry_recorded",
                "name": student.name,
                "roll_no": student.roll_number,
                "roll_number": student.roll_number,
                "paid": "YES",
                "entry_time": formatted_entry,
                "exit_time": None,
                "message": "ENTRY RECORDED",
                "student": student.to_dict()
            }

    # Step 3: ATOMIC EXIT TRANSITION (entry_time IS NOT NULL AND exit_time IS NULL)
    if dialect == "postgresql":
        raw_sql_exit = text("""
            UPDATE registrations
            SET exit_time = :now_ist
            WHERE roll_number = :roll_number
              AND registered = TRUE
              AND entry_time IS NOT NULL
              AND exit_time IS NULL
            RETURNING roll_number, name, entry_time, exit_time;
        """)
        res = db.execute(raw_sql_exit, {"roll_number": clean_roll, "now_ist": now_ist})
        row_exit = res.fetchone()
        db.commit()

        if row_exit:
            formatted_entry = parse_and_format_ist(row_exit.entry_time, time_only=True) or "—"
            formatted_exit = parse_and_format_ist(row_exit.exit_time, time_only=True) or now_ist.strftime("%I:%M:%S %p")
            return {
                "status": "exit_recorded",
                "name": row_exit.name,
                "roll_no": row_exit.roll_number,
                "roll_number": row_exit.roll_number,
                "paid": "YES",
                "entry_time": formatted_entry,
                "exit_time": formatted_exit,
                "message": "EXIT RECORDED",
                "student": {
                    "roll_number": row_exit.roll_number,
                    "roll_no": row_exit.roll_number,
                    "name": row_exit.name,
                    "paid": "YES",
                    "entry_time": formatted_entry,
                    "exit_time": formatted_exit,
                    "status": "EXITED"
                }
            }
    else:
        updated_exit = db.query(Student).filter(
            Student.roll_number == clean_roll,
            Student.registered == True,
            Student.entry_time != None,
            Student.exit_time == None
        ).update(
            {Student.exit_time: now_ist},
            synchronize_session=False
        )
        db.commit()

        if updated_exit > 0:
            db.refresh(student)
            formatted_entry = parse_and_format_ist(student.entry_time, time_only=True) or "—"
            formatted_exit = parse_and_format_ist(student.exit_time, time_only=True) or now_ist.strftime("%I:%M:%S %p")
            return {
                "status": "exit_recorded",
                "name": student.name,
                "roll_no": student.roll_number,
                "roll_number": student.roll_number,
                "paid": "YES",
                "entry_time": formatted_entry,
                "exit_time": formatted_exit,
                "message": "EXIT RECORDED",
                "student": student.to_dict()
            }

    # Step 4: ALREADY EXITED (entry_time IS NOT NULL AND exit_time IS NOT NULL)
    db.refresh(student)
    formatted_entry = parse_and_format_ist(student.entry_time, time_only=True) or "—"
    formatted_exit = parse_and_format_ist(student.exit_time, time_only=True) or "—"

    return {
        "status": "already_exited",
        "name": student.name,
        "roll_no": student.roll_number,
        "roll_number": student.roll_number,
        "paid": "YES" if student.registered else "NO",
        "entry_time": formatted_entry,
        "exit_time": formatted_exit,
        "message": "ALREADY EXITED",
        "student": student.to_dict()
    }
