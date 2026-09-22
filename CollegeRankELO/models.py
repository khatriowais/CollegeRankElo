"""
models.py
---------
SQLAlchemy ORM models for CollegeRankELO.
"""

from datetime import datetime
from sqlalchemy import (Column, Integer, String, Float, Boolean, DateTime,
                        ForeignKey, Text, UniqueConstraint, Index)
from sqlalchemy.orm import relationship
from database import Base


class College(Base):
    __tablename__ = "colleges"

    id = Column(Integer, primary_key=True)
    # No longer globally unique: the same college name can exist in different
    # countries. Uniqueness is enforced per-country below.
    college_name = Column(String(255), nullable=False)
    city = Column(String(80))
    region = Column(String(120))       # state / province
    country = Column(String(80))
    type = Column(String(40))          # Aided / Unaided / Government
    university = Column(String(160))
    naac_grade = Column(String(8))
    nirf_rank = Column(Integer)
    annual_fee = Column(Integer)
    average_package = Column(Integer)
    highest_package = Column(Integer)
    placement_percentage = Column(Float)
    student_rating = Column(Float)
    website = Column(String(255))
    logo = Column(String(255))

    # Cohort / provenance (multi-cohort support).
    cohort = Column(String(40))         # e.g. 'mumbai', 'india'
    currency = Column(String(8))        # e.g. 'INR', 'USD'
    data_source = Column(String(40))    # e.g. 'mumbai_curated', 'hipolabs'
    source_url = Column(String(255))
    # Gates the leaderboard and head-to-head compare. Directory-only rows
    # (no verified metrics) are is_ranked=False and never receive an Elo.
    is_ranked = Column(Boolean, default=False)
    courses = Column(Text)              # JSON list of course dicts

    elo_rating = Column(Float, default=1500.0)
    last_updated = Column(DateTime, default=datetime.utcnow,
                          onupdate=datetime.utcnow)

    history = relationship("EloHistory", back_populates="college",
                           cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("college_name", "country", name="uq_college_country"),
        Index("ix_cohort_elo", "cohort", "elo_rating"),
        Index("ix_college_country", "country"),
        Index("ix_college_is_ranked", "is_ranked"),
        Index("ix_college_name", "college_name"),
    )

    def to_dict(self) -> dict:
        import json
        ranked = bool(self.is_ranked)
        parsed_courses = []
        if self.courses:
            try:
                parsed_courses = json.loads(self.courses) if isinstance(self.courses, str) else self.courses
            except Exception:
                parsed_courses = []
        return {
            "id": self.id,
            "college_name": self.college_name,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "cohort": self.cohort,
            "currency": self.currency or "INR",
            "data_source": self.data_source,
            "source_url": self.source_url,
            "is_ranked": ranked,
            "type": self.type,
            "university": self.university,
            "naac_grade": self.naac_grade,
            "nirf_rank": self.nirf_rank,
            "annual_fee": self.annual_fee,
            "average_package": self.average_package,
            "highest_package": self.highest_package,
            "placement_percentage": self.placement_percentage,
            "student_rating": self.student_rating,
            "courses": parsed_courses,
            "website": self.website,
            "logo": self.logo,
            # Directory-only rows are not Elo-ranked: report None, not a fake 1500.
            "elo_rating": (round(self.elo_rating, 2)
                           if ranked and self.elo_rating is not None else None),
            # ROI is None (not a misleading 0) when we don't have both figures.
            "roi": (round(self.average_package / self.annual_fee, 2)
                    if self.average_package is not None and self.annual_fee
                    else None),
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
