from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    category: str
    quantity: float = Field(ge=0)
    unit: str
    price: float = Field(gt=0)
    minimum_stock: float = Field(default=5, ge=0)


class StockUpdate(BaseModel):
    quantity: float = Field(gt=0)