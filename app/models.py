from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

def parse_and_format_ist(val):
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
        return dt.strftime("%d %b %Y, %I:%M:%S %p IST")
    return str(val)

class Student(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    token = Column(String(100), nullable=True, default="")
    registered = Column(Boolean, default=True, nullable=False)
    checked_in = Column(Boolean, default=False, nullable=False)
    checked_in_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "name": self.name,
            "registered": self.registered,
            "checked_in": self.checked_in,
            "checked_in_at": parse_and_format_ist(self.checked_in_at)
        }
