from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SearchHistory(Base):
    """Har search ka record."""
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    meter_id = Column(Integer, ForeignKey("meters.id"), nullable=True)
    reference_no = Column(String, index=True)
    disco = Column(String, default="fesco")
    consumer_name = Column(String, nullable=True)
    units = Column(Integer, nullable=True)
    grand_total = Column(Integer, nullable=True)
    alert_status = Column(String, nullable=True)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="searches")
    meter = relationship("Meter", back_populates="searches")


class CachedBill(Base):
    """FESCO se fetch kiya hua bill ka cache."""
    __tablename__ = "cached_bills"

    id = Column(Integer, primary_key=True, index=True)
    reference_no = Column(String, index=True)
    disco = Column(String, default="fesco")
    bill_data = Column(Text)  # JSON string
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())