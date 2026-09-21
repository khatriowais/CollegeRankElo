"""
models.py
---------
SQLAlchemy ORM models for CollegeRankELO.
"""

from datetime import datetime
from sqlalchemy import (Column, Integer, String, Float, DateTime, ForeignKey,
                        Text)
from sqlalchemy.orm import relationship
from database import Base


class College(Base):
    __tablename__ = "colleges"

    id = Column(Integer, primary_key=True)
    college_name = Column(String(255), nullable=False, unique=True)
    city = Column(String(80))
    type = Column(String(40))          # Government / Private
    university = Column(String(120))
    naac_grade = Column(String(8))
    nirf_rank = Column(Integer)
    annual_fee = Column(Integer)
    average_package = Column(Integer)
    highest_package = Column(Integer)
    placement_percentage = Column(Float)
    student_rating = Column(Float)
    website = Column(String(255))
    logo = Column(String(255))
    elo_rating = Column(Float, default=1500.0)
    last_updated = Column(DateTime, default=datetime.utcnow,
                          onupdate=datetime.utcnow)

    history = relationship("EloHistory", back_populates="college",
                           cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "college_name": self.college_name,
            "city": self.city,
            "type": self.type,
            "university": self.university,
            "naac_grade": self.naac_grade,
            "nirf_rank": self.nirf_rank,
            "annual_fee": self.annual_fee,
            "average_package": self.average_package,
            "highest_package": self.highest_package,
            "placement_percentage": self.placement_percentage,
            "student_rating": self.student_rating,
            "website": self.website,
            "logo": self.logo,
            "elo_rating": round(self.elo_rating or 1500.0, 2),
            "roi": round((self.average_package or 0) /
                         max(1, self.annual_fee or 1), 2),
            "last_updated": self.last_updated.isoformat()
                            if self.last_updated else None,
        }


class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True)
    college_a_id = Column(Integer, ForeignKey("colleges.id"), nullable=False)
    college_b_id = Column(Integer, ForeignKey("colleges.id"), nullable=False)
    winner = Column(String(10))            # 'A', 'B' or 'DRAW'
    score_a = Column(Float)
    score_b = Column(Float)
    breakdown_a = Column(Text)             # JSON blob
    breakdown_b = Column(Text)
    old_elo_a = Column(Float)
    old_elo_b = Column(Float)
    new_elo_a = Column(Float)
    new_elo_b = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    college_a = relationship("College", foreign_keys=[college_a_id])
    college_b = relationship("College", foreign_keys=[college_b_id])


class EloHistory(Base):
    __tablename__ = "elo_history"

    id = Column(Integer, primary_key=True)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=False)
    rating = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    college = relationship("College", back_populates="history")
