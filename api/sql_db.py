"""MySQL connection and table definitions (SQLAlchemy ORM).

Tables: countries, customers, products, invoices, invoice_lines.
One row in invoice_lines is one product line of an invoice, which is
the same granularity as the cleaned dataset from Task 1.
"""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, Numeric, String,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from api.config import MYSQL_URL

engine = create_engine(MYSQL_URL, pool_pre_ping=True)

# Codes are case-sensitive in the data (e.g. 15056BL and 15056bl are different products),
# so they use a binary collation instead of MySQL's case-insensitive default
Code = String(20, collation="utf8mb4_bin")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Country(Base):
    __tablename__ = "countries"
    country_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)


class Customer(Base):
    __tablename__ = "customers"
    # Missing customer IDs are stored as "UNKNOWN" so foreign keys stay valid (Task 1, Step 3)
    customer_id: Mapped[str] = mapped_column(Code, primary_key=True)


class Product(Base):
    __tablename__ = "products"
    stock_code: Mapped[str] = mapped_column(Code, primary_key=True)
    description: Mapped[str | None] = mapped_column(String(255))


class Invoice(Base):
    __tablename__ = "invoices"
    invoice_no: Mapped[str] = mapped_column(Code, primary_key=True)
    invoice_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    customer_id: Mapped[str] = mapped_column(Code, ForeignKey("customers.customer_id"), index=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.country_id"))
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    country: Mapped[Country] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    line_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_no: Mapped[str] = mapped_column(Code, ForeignKey("invoices.invoice_no"), index=True)
    stock_code: Mapped[str] = mapped_column(Code, ForeignKey("products.stock_code"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 3))

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()



def get_session():
    """FastAPI dependency that opens one session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_sql():
    Base.metadata.create_all(engine)
