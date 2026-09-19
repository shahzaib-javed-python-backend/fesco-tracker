from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Meter(Base):
    """User ka saved meter (reference number)."""
    __tablename__ = "meters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reference_no = Column(String, index=True, nullable=False)
    disco = Column(String, default="fesco")
    nickname = Column(String, nullable=True)  # Jaise "Ghar", "Dukaan"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="meters")
    searches = relationship("SearchHistory", back_populates="meter")