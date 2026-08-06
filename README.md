# Student Lunch QR Verification Web Application

A lightweight, robust, high-performance web application for verifying student lunch eligibility using pre-existing QR codes at college events (~1,200 students, 5–10 concurrent mobile scanners).

---

## Technical Stack
* **Backend**: Python 3.10+, FastAPI, SQLAlchemy, openpyxl, Uvicorn
* **Database**: PostgreSQL (Atomic `UPDATE ... WHERE ... RETURNING` for zero race conditions)
* **Frontend**: HTML5, Vanilla JavaScript, Bootstrap 5, `html5-qrcode` library

---

## 1. PostgreSQL Setup

### Step A: Install PostgreSQL
Download and install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/) (or via `sudo apt install postgresql` on Linux / `brew install postgresql` on macOS).

### Step B: Create Database & User
Open `psql` shell or pgAdmin and run:

```sql
CREATE DATABASE student_lunch_db;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE student_lunch_db TO postgres;
```

---

## 2. Installation Commands

Navigate into the project directory and create a virtual environment:

```bash
cd student-lunch-system

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
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/student_lunch_db
```

*(Note: SQLite fallback is also supported out-of-the-box for quick zero-setup testing: `DATABASE_URL=sqlite:///./local_test.db`)*

### Step B: Start FastAPI Server
Run Uvicorn server bound to all local network interfaces (`0.0.0.0`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. How to Upload the Excel File

### Option 1: Via Admin Web Dashboard
1. Open `http://localhost:8000/admin` in your browser.
2. Click **Upload Excel**.
3. Select `sample_students.xlsx` (or generate a new one using `python generate_sample_data.py`).
4. Click **Upload & Process**. All 1,200 records will be imported automatically into PostgreSQL.

### Option 2: Generate Sample Excel
Generate sample data locally anytime:
```bash
python generate_sample_data.py
```

---

## 5. How to Test QR Scanning

### Method A: Scanning with Phone Camera
1. Open `http://<YOUR_LOCAL_IP>:8000/scanner` on your mobile phone or desktop browser.
2. Grant camera permissions.
3. Point camera at a QR code containing a valid student token (e.g. `ABC123` for Student A, `XYZ456` for Student B).

### Method B: Manual Input / Test Script
1. Expand the **Manual Token Input** section on the scanner page.
2. Enter token `ABC123` and click Submit.
   - 1st scan: `✅ ENTRY ALLOWED`
   - 2nd scan: `❌ ALREADY USED` (Shows student name & original timestamp)
3. Enter token `XYZ456` (Student B who opted NO):
   - Returns `❌ NOT ELIGIBLE`
4. Enter token `UNKNOWN999`:
   - Returns `❌ INVALID QR`

### Method C: Run Concurrency Race Condition Test
Simulate 10 phones scanning the exact same QR code simultaneously:
```bash
python test_concurrency.py
```
Expected output: Exactly 1 phone receives `✅ ALLOWED`, while 9 phones receive `❌ ALREADY USED`.

---

## 6. How to Access Scanner from Mobile Phones

Mobile browsers (Chrome / Safari) **require HTTPS** or a secure context to grant camera access.

### Quick Local Testing via ngrok (Recommended for Local WiFi)
1. Install [ngrok](https://ngrok.com/).
2. Run ngrok tunnel on port 8000:
   ```bash
   ngrok http 8000
   ```
3. Copy the secure HTTPS URL (e.g., `https://abc1234.ngrok-free.app/scanner`).
4. Open this URL on all mobile phones.

---

## 7. How to Deploy Online (Production Setup)

### Option 1: Render / Railway / Fly.io (Free & Easy)
1. Push repository to GitHub.
2. Provision a PostgreSQL instance on Railway / Render.
3. Connect repository to Render / Railway:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable:
   `DATABASE_URL=postgresql://user:password@host:5432/dbname`
5. Deploy! Both SSL/HTTPS camera access and database persistence are handled automatically.

### Option 2: Linux VPS (Ubuntu + Nginx + Certbot SSL + Systemd)
1. **Systemd Service (`/etc/systemd/system/lunch-app.service`)**:
   ```ini
   [Unit]
   Description=FastAPI Student Lunch Service
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/student-lunch-system
   ExecStart=/home/ubuntu/student-lunch-system/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4

   [Install]
   WantedBy=multi-user.target
   ```
2. **Nginx Reverse Proxy with Free HTTPS**:
   ```nginx
   server {
       server_name lunch.yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
3. **Enable SSL**:
   ```bash
   sudo certbot --nginx -d lunch.yourdomain.com
   ```
