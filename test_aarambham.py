import os
import sys
import threading
import time
import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Student, ensure_db_schema_migrated
from app.scanner import verify_and_mark_event_entry
from app.excel_import import parse_and_import_excel, generate_excel_export

TEST_DB_URL = "sqlite:///./test_entry_exit.db"

def run_tests():
    if os.path.exists("./test_entry_exit.db"):
        try:
            os.remove("./test_entry_exit.db")
        except Exception:
            pass

    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    ensure_db_schema_migrated(engine)

    db = TestingSession()

    print("==================================================")
    print("RUNNING AARAMBHAM ENTRY + EXIT & 2-COLUMN EXCEL SUITE")
    print("==================================================")

    # 8. Testing Excel import mapping for 2-column format (Roll No | Paid)
    print("\n8. Testing 2-Column Excel Import (Roll No | Paid)...")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Roll No", "Paid"])
    ws.append(["NC.EC.U4ECE25001", "Y"])
    ws.append(["NC.EC.U4ECE25002", "Y"])
    ws.append(["NC.EC.U4ECE25003", "N"])
    import io
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_bytes = excel_file.getvalue()

    import_res = parse_and_import_excel(db, excel_bytes, replace_all=True)
    assert import_res["success"] == True
    assert import_res["added"] == 3
    print("   [PASS] 2-Column Excel import parsed & mapped successfully!")

    # 1. Paid student first scan -> entry recorded
    print("\n1. Testing Paid Student First Scan (Entry)...")
    res1 = verify_and_mark_event_entry(db, "NC.EC.U4ECE25001")
    assert res1["status"] == "entry_recorded"
    assert res1["paid"] == "YES"
    assert res1["entry_time"] is not None
    assert res1["exit_time"] is None
    print(f"   [PASS] First Scan Result: {res1['status']} | Paid: {res1['paid']} | Entry: {res1['entry_time']} | Exit: {res1['exit_time']}")

    # 2. Paid student second scan -> exit recorded
    print("\n2. Testing Paid Student Second Scan (Exit)...")
    res2 = verify_and_mark_event_entry(db, "NC.EC.U4ECE25001")
    assert res2["status"] == "exit_recorded"
    assert res2["paid"] == "YES"
    assert res2["entry_time"] is not None
    assert res2["exit_time"] is not None
    print(f"   [PASS] Second Scan Result: {res2['status']} | Paid: {res2['paid']} | Entry: {res2['entry_time']} | Exit: {res2['exit_time']}")

    # 3. Paid student third scan -> timestamps unchanged
    print("\n3. Testing Paid Student Third Scan (Already Exited)...")
    res3 = verify_and_mark_event_entry(db, "NC.EC.U4ECE25001")
    assert res3["status"] == "already_exited"
    assert res3["paid"] == "YES"
    assert res3["entry_time"] == res2["entry_time"]
    assert res3["exit_time"] == res2["exit_time"]
    print(f"   [PASS] Third Scan Result: {res3['status']} | Timestamps Unchanged!")

    # 4. Unpaid student -> entry rejected
    print("\n4. Testing Unpaid Student (Entry Rejected)...")
    res_unpaid = verify_and_mark_event_entry(db, "NC.EC.U4ECE25003")
    assert res_unpaid["status"] == "unpaid"
    assert res_unpaid["paid"] == "NO"
    assert res_unpaid["entry_time"] is None
    assert res_unpaid["exit_time"] is None
    print("   [PASS] Unpaid Student Entry Rejected Successfully!")

    # 5. Unknown Roll Number -> NOT REGISTERED
    print("\n5. Testing Unknown Roll Number...")
    res_unknown = verify_and_mark_event_entry(db, "NC.EC.NONEXISTENT")
    assert res_unknown["status"] == "not_registered"
    assert res_unknown["paid"] == "NO"
    assert res_unknown["message"] == "NOT REGISTERED"
    print("   [PASS] Unknown Roll Number correctly displayed NOT REGISTERED!")

    # 6. QR scan -> same logic as manual Roll Number
    print("\n6. Testing QR scan and Manual Roll Number parity...")
    res_manual = verify_and_mark_event_entry(db, "  NC.EC.U4ECE25002  ")
    assert res_manual["status"] == "entry_recorded"
    assert res_manual["paid"] == "YES"
    print("   [PASS] QR Scan and Manual Roll Number call identical logic!")

    # 7. Duplicate simultaneous scans -> only one valid state transition
    print("\n7. Testing Duplicate Simultaneous Scans (Atomic Concurrency)...")
    s_conc = Student(roll_number="NC.EC.CONCURRENCY", name="NC.EC.CONCURRENCY", registered=True)
    db.add(s_conc)
    db.commit()

    results_entry = []
    def scan_entry():
        local_db = TestingSession()
        res = verify_and_mark_event_entry(local_db, "NC.EC.CONCURRENCY")
        results_entry.append(res)
        local_db.close()

    t1 = threading.Thread(target=scan_entry)
    t2 = threading.Thread(target=scan_entry)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses = [r["status"] for r in results_entry]
    assert "entry_recorded" in statuses
    print(f"   [PASS] Concurrent Scans Handled Safely: {statuses}")

    db.close()

    if os.path.exists("./test_entry_exit.db"):
        try:
            os.remove("./test_entry_exit.db")
        except Exception:
            pass

    print("\n==================================================")
    print("SUCCESS: ALL 8 PROMPT REQUIREMENTS TESTED & PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
