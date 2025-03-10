from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
from typing import List
import csv
import enum

DATABASE_URL = "sqlite:///./events.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class EventStatus(enum.Enum):
    scheduled = "scheduled"
    ongoing = "ongoing"
    completed = "completed"
    canceled = "canceled"

class Event(Base):
    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(String)
    max_attendees = Column(Integer)
    status = Column(Enum(EventStatus), default=EventStatus.scheduled)
    attendees = relationship("Attendee", back_populates="event")

class Attendee(Base):
    __tablename__ = "attendees"
    attendee_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    check_in_status = Column(Boolean, default=False)
    event = relationship("Event", back_populates="attendees")

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/events/")
def create_event(name: str, description: str, start_time: datetime, end_time: datetime, location: str, max_attendees: int, db: SessionLocal = Depends(get_db)):
    event = Event(name=name, description=description, start_time=start_time, end_time=end_time, location=location, max_attendees=max_attendees)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@app.put("/events/{event_id}")
def update_event(event_id: int, status: EventStatus, db: SessionLocal = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = status
    db.commit()
    return event

@app.post("/attendees/")
def register_attendee(event_id: int, first_name: str, last_name: str, email: str, phone_number: str, db: SessionLocal = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if len(event.attendees) >= event.max_attendees:
        raise HTTPException(status_code=400, detail="Event is full")
    attendee = Attendee(event_id=event_id, first_name=first_name, last_name=last_name, email=email, phone_number=phone_number)
    db.add(attendee)
    db.commit()
    db.refresh(attendee)
    return attendee

@app.post("/attendees/check-in/{attendee_id}")
def check_in_attendee(attendee_id: int, db: SessionLocal = Depends(get_db)):
    attendee = db.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
    if not attendee:
        raise HTTPException(status_code=404, detail="Attendee not found")
    attendee.check_in_status = True
    db.commit()
    return attendee

@app.get("/events/")
def list_events(status: EventStatus = None, location: str = None, date: datetime = None, db: SessionLocal = Depends(get_db)):
    query = db.query(Event)
    if status:
        query = query.filter(Event.status == status)
    if location:
        query = query.filter(Event.location == location)
    if date:
        query = query.filter(Event.start_time >= date, Event.end_time <= date + timedelta(days=1))
    return query.all()

@app.get("/events/{event_id}/attendees")
def list_attendees(event_id: int, db: SessionLocal = Depends(get_db)):
    return db.query(Attendee).filter(Attendee.event_id == event_id).all()

@app.post("/attendees/bulk-check-in/")
def bulk_check_in(file: UploadFile = File(...), db: SessionLocal = Depends(get_db)):
    reader = csv.reader(file.file.read().decode("utf-8").splitlines())
    for row in reader:
        attendee_id = int(row[0])
        attendee = db.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
        if attendee:
            attendee.check_in_status = True
    db.commit()
    return {"message": "Bulk check-in completed"}
