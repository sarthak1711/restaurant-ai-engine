from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, ForeignKey, Text,Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(Integer,primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100),nullable=False)
    phone_no = Column(String(100))
    address = Column(String(100))
    suburb = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    zip_code = Column(String(10))
    
    categories = relationship(
        "Category",
        back_populates="business_profile",
        cascade="all, delete-orphan"
    )
    items = relationship(
        "Item",
        back_populates="business_profile",
        cascade="all, delete-orphan"
    )
    customers = relationship(
        "Customer",
        back_populates="business_profile",
        cascade="save-update, merge"
    )
    orders = relationship(
        "Order",
        back_populates="business_profile",
        cascade="save-update, merge"
    )

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer,primary_key=True)
    business_id  = Column(Integer,ForeignKey('business_profiles.id'), nullable=False)
    category_name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)
    business_profile = relationship(
        "BusinessProfile",
        back_populates="categories"
    )
    items = relationship(
        "Item",
        back_populates="category",
        cascade="all, delete-orphan"
    )

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer,primary_key=True)
    business_id = Column(Integer,ForeignKey('business_profiles.id'), nullable=False)
    category_id = Column(Integer,ForeignKey('categories.id'), nullable=False)
    item_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    active = Column(Boolean, default=True)
    
    business_profile = relationship(
        "BusinessProfile",
        back_populates="items"
    )
    
    category = relationship(
        "Category",
        back_populates="items"
    )

    order_line_items = relationship(
        "OrderLineItem",
        back_populates="item",
        cascade="save-update, merge"
    )

class Customer(Base):
    __tablename__ ="customers"
    id = Column(Integer,primary_key=True)
    business_id = Column(Integer,ForeignKey('business_profiles.id'), nullable=False)
    customer_name = Column(String(100),nullable=False)
    customer_email = Column(String(100),nullable=False)
    segment = Column(String(100),nullable=False)
    business_profile = relationship(
        "BusinessProfile",
        back_populates="customers"
    )
    orders = relationship(
        "Order",
        back_populates="customer",
        cascade="save-update, merge"
    )

class Order(Base):
    __tablename__="orders"
    id = Column(Integer,primary_key=True)
    business_id = Column(Integer,ForeignKey('business_profiles.id'), nullable=False)
    customer_id = Column(Integer,ForeignKey('customers.id'), nullable=False)
    order_date = Column(DateTime,nullable=False)
    status = Column(String(100),nullable=False)
    payment_mode = Column(String(100),nullable=False)
    discount = Column(Float,nullable=False, default=0.0)
    total = Column(Float,nullable=False)
    tax = Column(Float,nullable=False, default=0.0)
    
    business_profile = relationship(
        "BusinessProfile",
        back_populates="orders"
    )
    
    customer = relationship(
        "Customer",
        back_populates="orders"
    )

    order_line_items = relationship(
        "OrderLineItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

class OrderLineItem(Base):
    __tablename__="order_line_items"
    id = Column(Integer,primary_key=True)
    order_id = Column(Integer,ForeignKey('orders.id'),nullable=False)
    item_id = Column(Integer,ForeignKey('items.id'),nullable=False)
    item_name = Column(String(100), nullable=False)
    item_price = Column(Float, nullable=False)
    item_discount = Column(Float,nullable=False, default=0.0)
    item_tax = Column(Float,nullable=False, default=0.0)
    
    order = relationship(
        "Order",
        back_populates="order_line_items"
    )

    item = relationship(
        "Item",
        back_populates="order_line_items"
    )

def create_tables():
    Base.metadata.create_all(engine)
    print("All tables created successfully")


if __name__ == "__main__":
    create_tables()