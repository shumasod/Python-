from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import List, Optional
import uvicorn
from enum import Enum

# データベース設定
SQLALCHEMY_DATABASE_URL = "sqlite:///./delivery_monitoring.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPIアプリケーション
app = FastAPI(
    title="配送実績モニタリングAPI",
    description="運送会社の配送実績を管理・モニタリングするためのAPI",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums
class DeliveryStatus(str, Enum):
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETURNED = "returned"

class VehicleType(str, Enum):
    TRUCK = "truck"
    VAN = "van"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"

# データベースモデル
class Driver(Base):
    __tablename__ = "drivers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    employee_id = Column(String, unique=True, nullable=False)
    phone = Column(String)
    license_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    deliveries = relationship("Delivery", back_populates="driver")

class Vehicle(Base):
    __tablename__ = "vehicles"
    
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, nullable=False)
    vehicle_type = Column(String, nullable=False)
    capacity_kg = Column(Float)
    fuel_efficiency = Column(Float)
    is_active = Column(Boolean, default=True)
    
    deliveries = relationship("Delivery", back_populates="vehicle")

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    email = Column(String)
    address = Column(String)
    postal_code = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    deliveries = relationship("Delivery", back_populates="customer")

class Delivery(Base):
    __tablename__ = "deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    tracking_number = Column(String, unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    
    pickup_address = Column(String, nullable=False)
    delivery_address = Column(String, nullable=False)
    package_weight = Column(Float)
    package_dimensions = Column(String)
    
    status = Column(String, default=DeliveryStatus.PENDING)
    priority = Column(Integer, default=1)  # 1: Low, 2: Medium, 3: High, 4: Urgent
    
    scheduled_pickup = Column(DateTime)
    actual_pickup = Column(DateTime)
    scheduled_delivery = Column(DateTime)
    actual_delivery = Column(DateTime)
    
    distance_km = Column(Float)
    delivery_fee = Column(Float)
    
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    customer = relationship("Customer", back_populates="deliveries")
    driver = relationship("Driver", back_populates="deliveries")
    vehicle = relationship("Vehicle", back_populates="deliveries")
    status_history = relationship("DeliveryStatusHistory", back_populates="delivery")

class DeliveryStatusHistory(Base):
    __tablename__ = "delivery_status_history"
    
    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(Integer, ForeignKey("deliveries.id"))
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(String)
    location = Column(String)
    
    delivery = relationship("Delivery", back_populates="status_history")

# Pydanticモデル
class DriverCreate(BaseModel):
    name: str
    employee_id: str
    phone: Optional[str] = None
    license_number: Optional[str] = None

class DriverResponse(BaseModel):
    id: int
    name: str
    employee_id: str
    phone: Optional[str]
    license_number: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class VehicleCreate(BaseModel):
    plate_number: str
    vehicle_type: VehicleType
    capacity_kg: Optional[float] = None
    fuel_efficiency: Optional[float] = None

class VehicleResponse(BaseModel):
    id: int
    plate_number: str
    vehicle_type: str
    capacity_kg: Optional[float]
    fuel_efficiency: Optional[float]
    is_active: bool
    
    class Config:
        from_attributes = True

class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None

class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    postal_code: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class DeliveryCreate(BaseModel):
    customer_id: int
    pickup_address: str
    delivery_address: str
    package_weight: Optional[float] = None
    package_dimensions: Optional[str] = None
    scheduled_pickup: Optional[datetime] = None
    scheduled_delivery: Optional[datetime] = None
    priority: int = Field(default=1, ge=1, le=4)
    delivery_fee: Optional[float] = None
    notes: Optional[str] = None

class DeliveryUpdate(BaseModel):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    status: Optional[DeliveryStatus] = None
    actual_pickup: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    distance_km: Optional[float] = None
    notes: Optional[str] = None

class DeliveryResponse(BaseModel):
    id: int
    tracking_number: str
    customer: Optional[CustomerResponse]
    driver: Optional[DriverResponse]
    vehicle: Optional[VehicleResponse]
    pickup_address: str
    delivery_address: str
    package_weight: Optional[float]
    status: str
    priority: int
    scheduled_pickup: Optional[datetime]
    actual_pickup: Optional[datetime]
    scheduled_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    distance_km: Optional[float]
    delivery_fee: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DeliveryStatistics(BaseModel):
    total_deliveries: int
    completed_deliveries: int
    pending_deliveries: int
    failed_deliveries: int
    completion_rate: float
    average_delivery_time_hours: Optional[float]
    total_distance_km: float
    total_revenue: float

class StatusUpdateRequest(BaseModel):
    status: DeliveryStatus
    notes: Optional[str] = None
    location: Optional[str] = None

# データベース依存関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 追跡番号生成
def generate_tracking_number() -> str:
    from uuid import uuid4
    return f"DLV{datetime.now().strftime('%Y%m%d')}{str(uuid4())[:8].upper()}"

# データベース初期化
Base.metadata.create_all(bind=engine)

# APIエンドポイント

# ドライバー管理
@app.post("/drivers/", response_model=DriverResponse)
def create_driver(driver: DriverCreate, db: Session = Depends(get_db)):
    db_driver = Driver(**driver.dict())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver

@app.get("/drivers/", response_model=List[DriverResponse])
def get_drivers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    drivers = db.query(Driver).filter(Driver.is_active == True).offset(skip).limit(limit).all()
    return drivers

@app.get("/drivers/{driver_id}", response_model=DriverResponse)
def get_driver(driver_id: int, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="ドライバーが見つかりません")
    return driver

# 車両管理
@app.post("/vehicles/", response_model=VehicleResponse)
def create_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db)):
    db_vehicle = Vehicle(**vehicle.dict())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle

@app.get("/vehicles/", response_model=List[VehicleResponse])
def get_vehicles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).offset(skip).limit(limit).all()
    return vehicles

# 顧客管理
@app.post("/customers/", response_model=CustomerResponse)
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    db_customer = Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@app.get("/customers/", response_model=List[CustomerResponse])
def get_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

# 配送管理
@app.post("/deliveries/", response_model=DeliveryResponse)
def create_delivery(delivery: DeliveryCreate, db: Session = Depends(get_db)):
    # 顧客の存在確認
    customer = db.query(Customer).filter(Customer.id == delivery.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="顧客が見つかりません")
    
    # 配送データ作成
    db_delivery = Delivery(
        **delivery.dict(),
        tracking_number=generate_tracking_number()
    )
    db.add(db_delivery)
    db.commit()
    db.refresh(db_delivery)
    
    # ステータス履歴を作成
    status_history = DeliveryStatusHistory(
        delivery_id=db_delivery.id,
        status=DeliveryStatus.PENDING,
        notes="配送依頼が作成されました"
    )
    db.add(status_history)
    db.commit()
    
    return db_delivery

@app.get("/deliveries/", response_model=List[DeliveryResponse])
def get_deliveries(
    skip: int = 0,
    limit: int = 100,
    status: Optional[DeliveryStatus] = None,
    driver_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Delivery)
    
    if status:
        query = query.filter(Delivery.status == status)
    if driver_id:
        query = query.filter(Delivery.driver_id == driver_id)
    if date_from:
        query = query.filter(Delivery.created_at >= date_from)
    if date_to:
        query = query.filter(Delivery.created_at <= date_to)
    
    deliveries = query.offset(skip).limit(limit).all()
    return deliveries

@app.get("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def get_delivery(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="配送が見つかりません")
    return delivery

@app.get("/deliveries/tracking/{tracking_number}", response_model=DeliveryResponse)
def track_delivery(tracking_number: str, db: Session = Depends(get_db)):
    delivery = db.query(Delivery).filter(Delivery.tracking_number == tracking_number).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="追跡番号が見つかりません")
    return delivery

@app.put("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def update_delivery(delivery_id: int, delivery_update: DeliveryUpdate, db: Session = Depends(get_db)):
    db_delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not db_delivery:
        raise HTTPException(status_code=404, detail="配送が見つかりません")
    
    # 更新データを適用
    for field, value in delivery_update.dict(exclude_unset=True).items():
        setattr(db_delivery, field, value)
    
    db_delivery.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

@app.post("/deliveries/{delivery_id}/status")
def update_delivery_status(
    delivery_id: int,
    status_update: StatusUpdateRequest,
    db: Session = Depends(get_db)
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="配送が見つかりません")
    
    # ステータス更新
    delivery.status = status_update.status
    delivery.updated_at = datetime.utcnow()
    
    # 特定のステータスの場合、時刻を記録
    if status_update.status == DeliveryStatus.PICKED_UP and not delivery.actual_pickup:
        delivery.actual_pickup = datetime.utcnow()
    elif status_update.status == DeliveryStatus.DELIVERED and not delivery.actual_delivery:
        delivery.actual_delivery = datetime.utcnow()
    
    # ステータス履歴を追加
    status_history = DeliveryStatusHistory(
        delivery_id=delivery_id,
        status=status_update.status,
        notes=status_update.notes,
        location=status_update.location
    )
    db.add(status_history)
    db.commit()
    
    return {"message": "ステータスが更新されました", "status": status_update.status}

# 統計・レポート
@app.get("/statistics/deliveries", response_model=DeliveryStatistics)
def get_delivery_statistics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Delivery)
    
    if date_from:
        query = query.filter(Delivery.created_at >= date_from)
    if date_to:
        query = query.filter(Delivery.created_at <= date_to)
    
    deliveries = query.all()
    
    total_deliveries = len(deliveries)
    completed_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.DELIVERED])
    pending_deliveries = len([d for d in deliveries if d.status in [DeliveryStatus.PENDING, DeliveryStatus.PICKED_UP, DeliveryStatus.IN_TRANSIT, DeliveryStatus.OUT_FOR_DELIVERY]])
    failed_deliveries = len([d for d in deliveries if d.status in [DeliveryStatus.FAILED, DeliveryStatus.RETURNED]])
    
    completion_rate = (completed_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
    
    # 平均配送時間計算
    delivery_times = []
    for d in deliveries:
        if d.actual_pickup and d.actual_delivery:
            delivery_time = (d.actual_delivery - d.actual_pickup).total_seconds() / 3600
            delivery_times.append(delivery_time)
    
    average_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else None
    
    total_distance = sum([d.distance_km for d in deliveries if d.distance_km]) or 0
    total_revenue = sum([d.delivery_fee for d in deliveries if d.delivery_fee]) or 0
    
    return DeliveryStatistics(
        total_deliveries=total_deliveries,
        completed_deliveries=completed_deliveries,
        pending_deliveries=pending_deliveries,
        failed_deliveries=failed_deliveries,
        completion_rate=round(completion_rate, 2),
        average_delivery_time_hours=round(average_delivery_time, 2) if average_delivery_time else None,
        total_distance_km=round(total_distance, 2),
        total_revenue=round(total_revenue, 2)
    )

@app.get("/statistics/drivers/{driver_id}")
def get_driver_statistics(
    driver_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Delivery).filter(Delivery.driver_id == driver_id)
    
    if date_from:
        query = query.filter(Delivery.created_at >= date_from)
    if date_to:
        query = query.filter(Delivery.created_at <= date_to)
    
    deliveries = query.all()
    
    total_deliveries = len(deliveries)
    completed_deliveries = len([d for d in deliveries if d.status == DeliveryStatus.DELIVERED])
    total_distance = sum([d.distance_km for d in deliveries if d.distance_km]) or 0
    
    return {
        "driver_id": driver_id,
        "total_deliveries": total_deliveries,
        "completed_deliveries": completed_deliveries,
        "completion_rate": round((completed_deliveries / total_deliveries * 100), 2) if total_deliveries > 0 else 0,
        "total_distance_km": round(total_distance, 2)
    }

# ヘルスチェック
@app.get("/health")
def health_check():
    return {"status": "OK", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
