# Aarambham Scanner — Event Registration & Entry Verification System

A lightweight, robust, high-performance web application for verifying student event registration and recording check-ins for the **Aarambham** event using QR codes / Roll Numbers (~1,200+ students, 5–10 concurrent mobile scanners).

---

## Technical Stack
* **Backend**: Python 3.10+, FastAPI, SQLAlchemy, openpyxl, Uvicorn
* **Database**: PostgreSQL (Atomic `UPDATE ... WHERE ... RETURNING` for zero race conditions across concurrent scanners) with SQLite fallback
* **Frontend**: HTML5, Vanilla JavaScript, Bootstrap 5, `html5-qrcode` library

---

## 1. Database Setup

### Step A: Install PostgreSQL (Optional, SQLite is built-in fallback)
Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/).

### Step B: Create Database & User
Open `psql` shell or pgAdmin and run:

```sql
CREATE DATABASE aarambham_db;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE aarambham_db TO postgres;
```

---

## 2. Installation Commands

Navigate into the project directory and create a virtual environment:

```bash
cd student-system

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 3. How to Run Locally

### Step A: Configure Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Ensure `DATABASE_URL` matches your PostgreSQL connection string:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aarambham_db
```

*(Note: SQLite fallback is supported out-of-the-box for quick zero-setup testing: `DATABASE_URL=sqlite:///./aarambham_event.db`)*

### Step B: Start FastAPI Server
Run Uvicorn server bound to all local network interfaces (`0.0.0.0`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. How to Upload Student Registrations (Excel)

### Option 1: Via Admin Web Dashboard
1. Open `http://localhost:8000/admin` in your browser.
2. Click **Upload Excel**.
3. Select an `.xlsx` file containing **Roll No** and **Name** columns (e.g., `sample_students.xlsx`).
4. Click **Upload & Process**. All student records will be imported automatically.

### Option 2: Generate Sample Excel Data
Generate sample data matching official roll number formats:
```bash
python generate_sample_data.py
```

---

## 5. How to Test Aarambham QR Scanning

### Method A: Scanning with Mobile/Web Camera
1. Open `http://<YOUR_LOCAL_IP>:8000/scanner` on your mobile phone or desktop browser.
2. Grant camera permissions.
3. Point camera at a student QR code containing their Roll Number (e.g. `NC.AI.U4AID24001`).

### Method B: Manual Roll Number Input
1. Expand **Manual Roll No Input** on the scanner page.
2. Enter Roll Number `NC.AI.U4AID24001` and click **Check**:
   - 1st scan: `🟢 REGISTERED — ENTRY ALLOWED`
   - 2nd scan: `🟡 ALREADY CHECKED IN` (Displays student name & previous check-in timestamp)
3. Enter an un-registered roll number (e.g., `INVALID.ROLL.999`):
   - Returns `🔴 NOT REGISTERED`

### Method C: Run Concurrency Race Condition Test
Simulate 10 scanners checking in the exact same student simultaneously:
```bash
python test_concurrency.py
```
Expected output: Exactly 1 scanner receives `🟢 ALLOWED`, while 9 scanners receive `🟡 ALREADY CHECKED IN`.

---

## 6. Accessing Scanner from Mobile Devices

Mobile browsers require HTTPS or localhost for camera access.

### Quick Testing via ngrok
1. Run ngrok on port 8000:
   ```bash
   ngrok http 8000
   ```
2. Open the secure HTTPS URL (e.g., `https://abc1234.ngrok-free.app/scanner`) on all scanner phones.

---

## 7. Production Deployment Setup

### Render / Railway / Fly.io
1. Push repository to GitHub.
2. Connect to Render / Railway with start command:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set `DATABASE_URL` environment variable.
4. SSL/HTTPS for camera access works out of the box!
