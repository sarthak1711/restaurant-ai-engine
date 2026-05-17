from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    country = Column(String(50), nullable=False)  # IN, AU, CA
    created_at = Column(DateTime)

    orders = relationship("Order", back_populates="restaurant")
    daily_revenues = relationship("DailyRevenue", back_populates="restaurant")
    customers = relationship("Customer", back_populates="restaurant")
    campaigns = relationship("Campaign", back_populates="restaurant")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="completed")  # completed, cancelled, refunded
    order_type = Column(String(20), default="dine_in")  # dine_in, delivery, takeaway
    created_at = Column(DateTime)

    restaurant = relationship("Restaurant", back_populates="orders")


class DailyRevenue(Base):
    __tablename__ = "daily_revenue"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    date = Column(Date, nullable=False)
    total_revenue = Column(Float, default=0.0)
    order_count = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0.0)

    restaurant = relationship("Restaurant", back_populates="daily_revenues")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    last_order_date = Column(Date)
    segment = Column(String(20), default="regular")  # vip, regular, at_risk, churned

    restaurant = relationship("Restaurant", back_populates="customers")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"))
    subject = Column(String(200))
    body = Column(Text)
    trigger_type = Column(String(50))  # lull_period, holiday, pre_stock
    status = Column(String(20), default="draft")  # draft, sent, failed
    created_at = Column(DateTime)
    sent_at = Column(DateTime, nullable=True)

    restaurant = relationship("Restaurant", back_populates="campaigns")


def create_tables():
    Base.metadata.create_all(engine)
    print("All tables created successfully")


if __name__ == "__main__":
    create_tables()