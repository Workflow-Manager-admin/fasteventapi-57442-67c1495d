"""
Main entry point for the Event Management FastAPI backend.
Implements RESTful APIs for CRUD operations on events.

OpenAPI docs available at /docs
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import sqlite3
from pathlib import Path


# ==== Database utility ====


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "events.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            location TEXT
        )
        """
    )
    conn.commit()
    conn.close()


# ==== Pydantic models ====


class EventBase(BaseModel):
    title: str = Field(..., description="The event title")
    description: Optional[str] = Field(None, description="Event description")
    start_time: datetime = Field(..., description="Event start date/time (ISO8601)")
    end_time: Optional[datetime] = Field(None, description="Event end date/time (ISO8601)")
    location: Optional[str] = Field(None, description="Event venue/location")


class EventCreate(EventBase):
    """Model for creating an event."""


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, description="The event title")
    description: Optional[str] = Field(None, description="Event description")
    start_time: Optional[datetime] = Field(None, description="Event start date/time (ISO8601)")
    end_time: Optional[datetime] = Field(None, description="Event end date/time (ISO8601)")
    location: Optional[str] = Field(None, description="Event venue/location")


class Event(EventBase):
    id: int = Field(..., description="Event ID")


# ==== FastAPI application setup ====


app = FastAPI(
    title="Event Management API",
    description="API-only backend service to create, manage, and retrieve events via RESTful endpoints.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Events", "description": "Operations for managing events (CRUD)"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ==== API ROUTES ====


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"])
def health_check():
    """
    Returns a health message that the backend is running.
    """
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post(
    "/events/",
    response_model=Event,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event",
    tags=["Events"],
    response_description="Created event details"
)
def create_event(event: EventCreate):
    """
    Create a new event.

    - **title**: Event title
    - **description**: Description (optional)
    - **start_time**: Start datetime (ISO8601)
    - **end_time**: End datetime (optional)
    - **location**: Location (optional)
    """
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (title, description, start_time, end_time, location) VALUES (?, ?, ?, ?, ?)",
        (
            event.title,
            event.description,
            event.start_time.isoformat(),
            event.end_time.isoformat() if event.end_time else None,
            event.location,
        ),
    )
    conn.commit()
    event_id = c.lastrowid
    row = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    event_id = row["id"]
    title = row["title"]
    description = row["description"]
    start_time = row["start_time"]
    end_time = row["end_time"]
    location = row["location"]
    return Event(
        id=event_id,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        location=location
    )


# PUBLIC_INTERFACE
@app.get(
    "/events/",
    response_model=List[Event],
    summary="List all events",
    tags=["Events"],
    response_description="List of all events"
)
def list_events():
    """
    Retrieve a list of all events.
    """
    conn = get_db()
    rows = conn.cursor().execute(
        "SELECT * FROM events ORDER BY start_time"
    ).fetchall()
    conn.close()
    events = [
        Event(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"],
        )
        for row in rows
    ]
    # Properly parse datetime fields for response model
    for ev in events:
        ev.start_time = datetime.fromisoformat(ev.start_time)
        ev.end_time = datetime.fromisoformat(ev.end_time) if ev.end_time else None
    return events


# PUBLIC_INTERFACE
@app.get(
    "/events/{event_id}/",
    response_model=Event,
    summary="Retrieve an event by ID",
    tags=["Events"],
    response_description="Event details"
)
def get_event(event_id: int):
    """
    Retrieve a single event by its ID.
    """
    conn = get_db()
    row = conn.cursor().execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    event = Event(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        location=row["location"],
    )
    # Parse to correct types
    event.start_time = datetime.fromisoformat(event.start_time)
    event.end_time = datetime.fromisoformat(event.end_time) if event.end_time else None
    return event


# PUBLIC_INTERFACE
@app.put(
    "/events/{event_id}/",
    response_model=Event,
    summary="Update an existing event",
    tags=["Events"],
    response_description="Updated event details"
)
def update_event(event_id: int, event_update: EventUpdate):
    """
    Update an event's details by its ID.
    """
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")

    # Prepare updated fields
    data = {
        "title": event_update.title if event_update.title is not None else row["title"],
        "description": event_update.description
        if event_update.description is not None
        else row["description"],
        "start_time": event_update.start_time.isoformat()
        if event_update.start_time is not None
        else row["start_time"],
        "end_time": event_update.end_time.isoformat()
        if event_update.end_time is not None
        else row["end_time"],
        "location": event_update.location if event_update.location is not None else row["location"],
    }

    c.execute(
        "UPDATE events SET title=?, description=?, start_time=?, end_time=?, location=? WHERE id=?",
        (
            data["title"],
            data["description"],
            data["start_time"],
            data["end_time"],
            data["location"],
            event_id,
        ),
    )
    conn.commit()
    updated_row = c.execute(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    conn.close()
    event_id = updated_row["id"]
    title = updated_row["title"]
    description = updated_row["description"]
    start_time = updated_row["start_time"]
    end_time = updated_row["end_time"]
    location = updated_row["location"]
    event = Event(
        id=event_id,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        location=location
    )
    event.start_time = datetime.fromisoformat(event.start_time)
    event.end_time = datetime.fromisoformat(event.end_time) if event.end_time else None
    return event


# PUBLIC_INTERFACE
@app.delete(
    "/events/{event_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event",
    tags=["Events"],
    response_class=JSONResponse,
    responses={204: {"description": "Event deleted"}}
)
def delete_event(event_id: int):
    """
    Delete an event by its ID.
    """
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")
    c.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
