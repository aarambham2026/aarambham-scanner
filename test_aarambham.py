import os
import sys
import threading
import time
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
    print("RUNNING AARAMBHAM ENTRY + EXIT SYSTEM TEST SUITE")
    print("==================================================")

    # Seed test student
    s1 = Student(roll_number="TEST.001", name="Alice Smith", registered=True)
    s2 = Student(roll_number="TEST.002", name="Bob Jones", registered=True)
    s_unreg = Student(roll_number="TEST.UNREG", name="Unregistered Charlie", registered=False)
    db.add_all([s1, s2, s_unreg])
    db.commit()

    # 1. First Scan -> Entry Recorded
    print("\n1. Testing First Scan (Entry)...")
    res1 = verify_and_mark_event_entry(db, "TEST.001")
    assert res1["status"] == "entry_recorded", f"Expected 'entry_recorded', got {res1['status']}"
    assert res1["message"] == "ENTRY RECORDED"
    assert res1["entry_time"] is not None
    assert res1["exit_time"] is None
    print(f"   [PASS] First Scan Result: {res1['status']} | Entry: {res1['entry_time']} | Exit: {res1['exit_time']}")

    # 2. Second Scan -> Exit Recorded
    print("\n2. Testing Second Scan (Exit)...")
    res2 = verify_and_mark_event_entry(db, "TEST.001")
    assert res2["status"] == "exit_recorded", f"Expected 'exit_recorded', got {res2['status']}"
    assert res2["message"] == "EXIT RECORDED"
    assert res2["entry_time"] is not None
    assert res2["exit_time"] is not None
    print(f"   [PASS] Second Scan Result: {res2['status']} | Entry: {res2['entry_time']} | Exit: {res2['exit_time']}")

    # 3. Third Scan -> Already Exited
    print("\n3. Testing Third Scan (Already Exited)...")
    res3 = verify_and_mark_event_entry(db, "TEST.001")
    assert res3["status"] == "already_exited", f"Expected 'already_exited', got {res3['status']}"
    assert res3["message"] == "ALREADY EXITED"
    print(f"   [PASS] Third Scan Result: {res3['status']} | Entry: {res3['entry_time']} | Exit: {res3['exit_time']}")

    # 4. Unknown / Unregistered Roll Number
    print("\n4. Testing Unregistered Roll Number...")
    res_unreg1 = verify_and_mark_event_entry(db, "TEST.UNREG")
    assert res_unreg1["status"] == "not_registered", f"Expected 'not_registered', got {res_unreg1['status']}"
    res_unreg2 = verify_and_mark_event_entry(db, "TEST.NONEXISTENT")
    assert res_unreg2["status"] == "not_registered", f"Expected 'not_registered', got {res_unreg2['status']}"
    print(f"   [PASS] Unregistered Scans Correctly Denied!")

    # 5. Two Simultaneous First Scans (Entry Concurrency)
    print("\n5. Testing Simultaneous First Scans (Entry Concurrency)...")
    s3 = Student(roll_number="TEST.CONCURRENCY", name="Concurrency User", registered=True)
    db.add(s3)
    db.commit()

    results_entry = []
    def scan_entry():
        local_db = TestingSession()
        res = verify_and_mark_event_entry(local_db, "TEST.CONCURRENCY")
        results_entry.append(res)
        local_db.close()

    t1 = threading.Thread(target=scan_entry)
    t2 = threading.Thread(target=scan_entry)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses_entry = [r["status"] for r in results_entry]
    assert "entry_recorded" in statuses_entry, "One scan must be 'entry_recorded'"
    assert "exit_recorded" in statuses_entry or "already_exited" in statuses_entry, "Second scan must transition to exit/already_exited"
    print(f"   [PASS] Concurrent Entry Scans Processed Safely: {statuses_entry}")

    # 6. Two Simultaneous Exit Scans (Exit Concurrency)
    print("\n6. Testing Simultaneous Exit Scans (Exit Concurrency)...")
    results_exit = []
    def scan_exit():
        local_db = TestingSession()
        res = verify_and_mark_event_entry(local_db, "TEST.CONCURRENCY")
        results_exit.append(res)
        local_db.close()

    t3 = threading.Thread(target=scan_exit)
    t4 = threading.Thread(target=scan_exit)
    t3.start()
    t4.start()
    t3.join()
    t4.join()

    statuses_exit = [r["status"] for r in results_exit]
    assert statuses_exit.count("already_exited") >= 1, "Subsequent concurrent exit scans must return 'already_exited'"
    print(f"   [PASS] Concurrent Exit Scans Processed Safely: {statuses_exit}")

    # 7. QR scan and manual scan use identical logic
    print("\n7. Testing QR scan and Manual input use identical logic...")
    res_qr = verify_and_mark_event_entry(db, "TEST.002")
    res_manual = verify_and_mark_event_entry(db, "  TEST.002  ")
    assert res_qr["status"] == "entry_recorded"
    assert res_manual["status"] == "exit_recorded"
    print("   [PASS] QR and Manual input produce identical state transitions!")

    # 8. Existing student records remain accessible after DB schema migration
    print("\n8. Testing existing student records accessibility after schema changes...")
    student_record = db.query(Student).filter(Student.roll_number == "TEST.001").first()
    assert student_record is not None
    dict_repr = student_record.to_dict()
    assert "entry_time" in dict_repr
    assert "exit_time" in dict_repr
    assert "status" in dict_repr
    print(f"   [PASS] Existing record accessed successfully: {dict_repr['name']} | Status: {dict_repr['status']}")

    db.close()

    if os.path.exists("./test_entry_exit.db"):
        try:
            os.remove("./test_entry_exit.db")
        except Exception:
            pass

    print("\n==================================================")
    print("SUCCESS: ALL 8 TEST CASES PASSED PERFECTLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
