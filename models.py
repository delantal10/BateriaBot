from __future__ import annotations
import json
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


class Listing(BaseModel):
    source: str
    external_id: Optional[str] = None
    url: Optional[str] = None

    title: str
    brand: Optional[str] = None
    model: Optional[str] = None

    voltage_v: Optional[float] = None
    capacity_ah: Optional[float] = None
    cca: Optional[int] = None
    polarity: Optional[str] = None

    price: float
    original_price: Optional[float] = None
    currency: str = "ARS"
    discount_pct: Optional[float] = None

    installments_qty: Optional[int] = None
    installment_amount: Optional[float] = None
    installment_rate: Optional[float] = None

    free_shipping: bool = False
    has_installation: bool = False
    delivery_available: bool = False

    seller_name: Optional[str] = None
    seller_id: Optional[str] = None
    seller_reputation: Optional[str] = None
    is_official_store: bool = False

    condition: Optional[str] = None
    available_quantity: Optional[int] = None
    sold_quantity: Optional[int] = None

    raw_data: Optional[str] = None  # JSON serializado

    catalog_model_id: Optional[str] = None  # FK a catalog (brand_modelcode)

    @field_validator("capacity_ah", mode="before")
    @classmethod
    def parse_capacity(cls, v):
        if isinstance(v, str):
            cleaned = v.replace(",", ".").split()[0]
            try:
                return float(cleaned)
            except ValueError:
                return None
        return v

    @field_validator("voltage_v", mode="before")
    @classmethod
    def parse_voltage(cls, v):
        if isinstance(v, str):
            cleaned = v.replace("V", "").replace(",", ".").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return v

    @field_validator("cca", mode="before")
    @classmethod
    def parse_cca(cls, v):
        if isinstance(v, str):
            cleaned = v.replace("A", "").strip()
            try:
                return int(float(cleaned))
            except ValueError:
                return None
        return v

    @model_validator(mode="after")
    def compute_discount(self) -> Listing:
        if self.original_price and self.original_price > self.price:
            self.discount_pct = round(
                (1 - self.price / self.original_price) * 100, 1
            )
        return self

    def raw_dict(self) -> dict:
        if self.raw_data:
            return json.loads(self.raw_data)
        return {}
