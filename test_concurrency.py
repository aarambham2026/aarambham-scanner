import concurrent.futures
import requests

BASE_URL = "http://127.0.0.1:8000"
ROLL_NO_TO_TEST = "CB.EN.U4AID23001"  # Student A (Opted: YES)

def send_scan(phone_id):
    try:
        response = requests.post(
            f"{BASE_URL}/api/scan",
            json={"roll_number": ROLL_NO_TO_TEST},
            timeout=5
        )
        return phone_id, response.json()
    except Exception as e:
        return phone_id, {"error": str(e)}

def run_concurrency_test(num_phones=10):
    print(f"Simulating {num_phones} simultaneous phone scans for Roll Number '{ROLL_NO_TO_TEST}'...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_phones) as executor:
        futures = [executor.submit(send_scan, i + 1) for i in range(num_phones)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    allowed_count = 0
    already_used_count = 0
    errors = 0

    print("\n--- RESULTS ---")
    for phone_id, res in sorted(results, key=lambda x: x[0]):
        status = res.get("status")
        print(f"Phone {phone_id}: {status} => {res.get('message')}")
        if status == "ALLOWED":
            allowed_count += 1
        elif status in ["ALREADY_CHECKED_IN", "ALREADY_USED"]:
            already_used_count += 1
        else:
            errors += 1

    print("\n--- CONCURRENCY SUMMARY ---")
    print(f"Total Phones Scanned: {num_phones}")
    print(f"ALLOWED (Success):   {allowed_count}")
    print(f"ALREADY CHECKED IN:  {already_used_count}")
    print(f"Errors/Invalid:      {errors}")

    if allowed_count == 1 and already_used_count == (num_phones - 1):
        print("\n✅ PASSED! Atomic DB update successfully prevented race conditions!")
    else:
        print("\n❌ FAILED! Multiple scans allowed or anomaly detected.")

if __name__ == "__main__":
    run_concurrency_test()
