from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, inspect, text
from app.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

def parse_and_format_ist(val, time_only: bool = False):
    if not val:
        return None
    dt = None
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, str):
        val_clean = val.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(val_clean)
        except Exception:
            try:
                dt = datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(val)
    else:
        return str(val)

    if dt:
        if dt.tzinfo is not None:
            dt = dt.astimezone(IST)
        if time_only:
            return dt.strftime("%I:%M:%S %p")
        return dt.strftime("%d %b %Y, %I:%M:%S %p IST")
    return str(val)


class Student(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    token = Column(String(100), nullable=True, default="")
    registered = Column(Boolean, default=True, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)

    @property
    def status(self) -> str:
        if not self.registered:
            return "NOT REGISTERED"
        if self.entry_time is None:
            return "NOT ENTERED"
        elif self.exit_time is None:
            return "INSIDE"
        else:
            return "EXITED"

    @property
    def checked_in(self) -> bool:
        return self.entry_time is not None

    def to_dict(self):
        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "roll_no": self.roll_number,
            "name": self.name,
            "registered": self.registered,
            "paid": "YES" if self.registered else "NO",
            "entry_time": parse_and_format_ist(self.entry_time),
            "exit_time": parse_and_format_ist(self.exit_time),
            "entry_time_display": parse_and_format_ist(self.entry_time, time_only=True) or "—",
            "exit_time_display": parse_and_format_ist(self.exit_time, time_only=True) or "—",
            "status": self.status,
            "checked_in": self.entry_time is not None,
            "checked_in_at": parse_and_format_ist(self.entry_time)
        }

def ensure_db_schema_migrated(engine):
    """
    Safely migrates existing database schema to include entry_time and exit_time columns.
    """
    try:
        inspector = inspect(engine)
        if "registrations" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("registrations")]
            with engine.begin() as conn:
                if "entry_time" not in columns:
                    conn.execute(text("ALTER TABLE registrations ADD COLUMN entry_time TIMESTAMP;"))
                if "exit_time" not in columns:
                    conn.execute(text("ALTER TABLE registrations ADD COLUMN exit_time TIMESTAMP;"))
                if "checked_in_at" in columns and "checked_in" in columns:
                    try:
                        conn.execute(text("UPDATE registrations SET entry_time = checked_in_at WHERE checked_in = TRUE AND entry_time IS NULL;"))
                    except Exception:
                        pass
    except Exception as e:
        print(f"Migration notice: {e}")
