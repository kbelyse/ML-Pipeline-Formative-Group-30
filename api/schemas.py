"""Request and response models shared by the SQL and MongoDB endpoints."""
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class TransactionIn(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=20, examples=["581587"])
    stock_code: str = Field(min_length=1, max_length=20, examples=["22613"])
    description: str | None = Field(default=None, max_length=255,
                                    examples=["PACK OF 20 SPACEBOY NAPKINS"])
    quantity: int = Field(examples=[12])
    invoice_date: datetime = Field(examples=["2011-12-09T12:50:00"])
    unit_price: float = Field(gt=0, examples=[0.85])
    customer_id: str = Field(default="UNKNOWN", max_length=20, examples=["12680"])
    country: str = Field(min_length=1, max_length=60, examples=["France"])

    @model_validator(mode="after")
    def check_quantity_sign(self):
        # Same rule as the Task 1 cleaning: cancellations (invoice starts with "C")
        # have negative quantities, normal sales have positive ones
        if self.invoice_no.upper().startswith("C"):
            if self.quantity >= 0:
                raise ValueError("cancelled invoices (starting with 'C') need a negative quantity")
        elif self.quantity <= 0:
            raise ValueError("sales need a positive quantity")
        return self


class TransactionUpdate(BaseModel):
    """All fields optional: only the fields sent are changed."""
    invoice_no: str | None = Field(default=None, min_length=1, max_length=20)
    stock_code: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=255)
    quantity: int | None = None
    invoice_date: datetime | None = None
    unit_price: float | None = Field(default=None, gt=0)
    customer_id: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, min_length=1, max_length=60)


class TransactionOut(TransactionIn):
    id: int | str
    is_cancelled: bool
    revenue: float

    # Stored records are trusted, so the sign check is not repeated on output
    @model_validator(mode="after")
    def check_quantity_sign(self):
        return self


class DailySummary(BaseModel):
    date: date
    gross_revenue: float
    net_revenue: float
    n_invoices: int
    total_quantity: int
    n_lines: int
