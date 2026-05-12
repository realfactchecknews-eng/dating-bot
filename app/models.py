from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Index, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(50))
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("Profile", back_populates="user", uselist=False)
    ratings_given = relationship("Rating", foreign_keys="Rating.rater_id", back_populates="rater")
    ratings_received = relationship("Rating", foreign_keys="Rating.rated_id", back_populates="rated")
    matches_as_user1 = relationship("Match", foreign_keys="Match.user1_id", back_populates="user1")
    matches_as_user2 = relationship("Match", foreign_keys="Match.user2_id", back_populates="user2")

class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    orientation = Column(String(20), nullable=False)
    city = Column(String(100))
    bio = Column(Text)
    photos = Column(JSON, default=list)
    psl_rating = Column(Float, default=0.0)
    appeal_rating = Column(Float, default=0.0)
    psl_votes_count = Column(Integer, default=0)
    appeal_votes_count = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="profile")
    
    __table_args__ = (
        Index('idx_profile_gender', 'gender'),
        Index('idx_profile_orientation', 'orientation'),
        Index('idx_profile_city', 'city'),
        Index('idx_profile_psl', 'psl_rating'),
        Index('idx_profile_appeal', 'appeal_rating'),
    )

class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True)
    rater_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rated_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    psl_score = Column(Integer, nullable=False)
    appeal_score = Column(Integer, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    rater = relationship("User", foreign_keys=[rater_id], back_populates="ratings_given")
    rated = relationship("User", foreign_keys=[rated_id], back_populates="ratings_received")
    
    __table_args__ = (
        Index('idx_rating_rater', 'rater_id'),
        Index('idx_rating_rated', 'rated_id'),
        Index('idx_rating_unique', 'rater_id', 'rated_id', unique=True),
    )

class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user1_liked = Column(Boolean, default=False)
    user2_liked = Column(Boolean, default=False)
    is_mutual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    matched_at = Column(DateTime)
    
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="matches_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="matches_as_user2")
    
    __table_args__ = (
        Index('idx_match_user1', 'user1_id'),
        Index('idx_match_user2', 'user2_id'),
        Index('idx_match_unique', 'user1_id', 'user2_id', unique=True),
    )

class Like(Base):
    __tablename__ = "likes"
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_like = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_like_from', 'from_user_id'),
        Index('idx_like_to', 'to_user_id'),
        Index('idx_like_unique', 'from_user_id', 'to_user_id', unique=True),
    )

class Statistic(Base):
    __tablename__ = "statistics"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    total_ratings = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)

class News(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    author_id = Column(Integer, ForeignKey("users.id"))

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_message_from_to', 'from_user_id', 'to_user_id'),
        Index('idx_message_created', 'created_at'),
    )

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text, nullable=False)
    report_type = Column(String(50), default="bug")  # bug, user, profile, other
    created_at = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)
