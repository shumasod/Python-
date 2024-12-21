# File: models.py
from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class Severity(enum.Enum):
    SEV1 = 1
    SEV2 = 2
    SEV3 = 3
    SEV4 = 4

class IncidentStatus(enum.Enum):
    DETECTED = "Detected"
    TRIAGED = "Triaged"
    MITIGATED = "Mitigated"
    RESOLVED = "Resolved"

class Incident(Base):
    __tablename__ = 'incidents'

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    description = Column(String)
    status = Column(Enum(IncidentStatus), default=IncidentStatus.DETECTED)
    detected_time = Column(DateTime, default=datetime.utcnow)
    resolved_time = Column(DateTime)
    assignee_id = Column(Integer, ForeignKey('users.id'))
    assignee = relationship("User", back_populates="assigned_incidents")
    updates = relationship("IncidentUpdate", back_populates="incident")

class IncidentUpdate(Base):
    __tablename__ = 'incident_updates'

    id = Column(Integer, primary_key=True)
    incident_id = Column(String, ForeignKey('incidents.id'))
    update_text = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    incident = relationship("Incident", back_populates="updates")

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    assigned_incidents = relationship("Incident", back_populates="assignee")

# File: database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DATABASE_URL = "sqlite:///./incident_management.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

# File: main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from models import Incident, IncidentUpdate, User, Severity, IncidentStatus
from database import SessionLocal, init_db
from pydantic import BaseModel
import smtplib
from email.message import EmailMessage
import slack_sdk

app = FastAPI()

# Security
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Slack client
SLACK_TOKEN = "your-slack-token"
slack_client = slack_sdk.WebClient(token=SLACK_TOKEN)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class IncidentCreate(BaseModel):
    title: str
    severity: Severity
    description: str

class IncidentUpdate(BaseModel):
    status: IncidentStatus = None
    assignee_id: int = None
    update_text: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

# User authentication
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password_hash):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# Notification functions
def send_email_notification(recipient: str, subject: str, body: str):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = "sre-alerts@example.com"
    msg['To'] = recipient

    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

def send_slack_notification(channel: str, message: str):
    try:
        slack_client.chat_postMessage(channel=channel, text=message)
    except Exception as e:
        print(f"Error sending Slack notification: {e}")

# API endpoints
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/incidents/", response_model=Incident)
async def create_incident(incident: IncidentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_incident = Incident(**incident.dict())
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    # Send notifications
    send_email_notification("sre-team@example.com", f"New Incident: {incident.title}", f"Severity: {incident.severity}\nDescription: {incident.description}")
    send_slack_notification("#sre-alerts", f"New Incident: {incident.title}\nSeverity: {incident.severity}\nDescription: {incident.description}")

    return db_incident

@app.put("/incidents/{incident_id}", response_model=Incident)
async def update_incident(incident_id: str, incident_update: IncidentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if db_incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident_update.status:
        db_incident.status = incident_update.status
    if incident_update.assignee_id:
        db_incident.assignee_id = incident_update.assignee_id
    if incident_update.update_text:
        new_update = IncidentUpdate(incident_id=incident_id, update_text=incident_update.update_text)
        db.add(new_update)

    db.commit()
    db.refresh(db_incident)

    # Send notifications
    send_email_notification("sre-team@example.com", f"Incident Update: {db_incident.title}", f"New status: {db_incident.status}\nUpdate: {incident_update.update_text}")
    send_slack_notification("#sre-alerts", f"Incident Update: {db_incident.title}\nNew status: {db_incident.status}\nUpdate: {incident_update.update_text}")

    return db_incident

@app.get("/incidents/", response_model=List[Incident])
async def list_incidents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incidents = db.query(Incident).offset(skip).limit(limit).all()
    return incidents

@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

@app.get("/metrics/")
async def get_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_incidents = db.query(Incident).count()
    open_incidents = db.query(Incident).filter(Incident.status != IncidentStatus.RESOLVED).count()
    sev1_incidents = db.query(Incident).filter(Incident.severity == Severity.SEV1).count()
    
    return {
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "sev1_incidents": sev1_incidents,
    }

if __name__ == "__main__":
    init_db()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
