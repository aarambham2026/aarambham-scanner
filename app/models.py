from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

class Student(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    token = Column(String(100), nullable=True, default="")
    lunch_opted = Column(Boolean, default=False, nullable=False)
    lunch_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        if isinstance(self.used_at, datetime):
            used_time_str = self.used_at.strftime("%d %b %Y, %I:%M:%S %p")
        elif self.used_at:
            used_time_str = str(self.used_at)
        else:
            used_time_str = None

        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "name": self.name,
            "lunch_opted": self.lunch_opted,
            "lunch_used": self.lunch_used,
            "used_at": used_time_str
        }
