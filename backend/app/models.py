import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    spotify_credentials = relationship("SpotifyCredentials", uselist=False, back_populates="user", cascade="all, delete-orphan")
    preference = relationship("UserPreference", uselist=False, back_populates="user", cascade="all, delete-orphan")
    interactions = relationship("UserInteraction", back_populates="user", cascade="all, delete-orphan")

class SpotifyCredentials(Base):
    __tablename__ = "spotify_credentials"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    encrypted_access_token = Column(String, nullable=False)
    encrypted_refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="spotify_credentials")

class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    rocchio_vector = Column(JSON, nullable=False) # List of 7 float features

    # Relationships
    user = relationship("User", back_populates="preference")

class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    track_id = Column(String, nullable=False)
    interaction_type = Column(String, nullable=False) # 'like', 'dislike', 'skip', 'remove'
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="interactions")
