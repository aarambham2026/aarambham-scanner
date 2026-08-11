from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

IST = timezone(timedelta(hours=5, minutes=30))

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
        if isinstance(self.checked_in_at, datetime):
            dt = self.checked_in_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc).astimezone(IST)
            else:
                dt = dt.astimezone(IST)
            checked_in_time_str = dt.strftime("%d %b %Y, %I:%M:%S %p IST")
        elif self.checked_in_at:
            checked_in_time_str = str(self.checked_in_at)
        else:
            checked_in_time_str = None

        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "name": self.name,
            "registered": self.registered,
            "checked_in": self.checked_in,
            "checked_in_at": checked_in_time_str
        }
