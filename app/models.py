from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

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
            checked_in_time_str = self.checked_in_at.strftime("%d %b %Y, %I:%M:%S %p")
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
