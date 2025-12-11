from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fullname = Column(String)
    username = Column(String, unique=True, nullable=False)
    email = Column(String)
    password = Column(String, nullable=False)
    
    events_created = relationship("Event", back_populates="creator")
    posts = relationship("CommunityPost", back_populates="author")
    event_participations = relationship("EventParticipant", back_populates="user")


class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text)
    datetime = Column(DateTime, nullable=False)  # Use proper DateTime type
    max_participants = Column(Integer, default=50)
    image = Column(String)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    collected_trash = Column(Integer, default=0)
    status = Column(String, default='Pending')
    holder_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # If holder references a user
    
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="events_created")
    holder = relationship("User", foreign_keys=[holder_id])
    participants_list = relationship("EventParticipant", back_populates="event")


class EventParticipant(Base):
    __tablename__ = 'event_participants'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    event = relationship("Event", back_populates="participants_list")
    user = relationship("User", back_populates="event_participations")


class CommunityPost(Base):
    __tablename__ = 'community_posts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    description = Column(Text, nullable=False)
    image = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    author = relationship("User", back_populates="posts")
