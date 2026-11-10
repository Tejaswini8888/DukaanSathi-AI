from pydantic import BaseModel, Field


class OrderItemRequest(BaseModel):
    product: str
    quantity: float = Field(gt=0)
    unit: str


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1)
    items: list[OrderItemRequest] = Field(min_length=1)


class OrderConfirmation(BaseModel):
    customer_name: str
    items: list[OrderItemRequest] = Field(min_length=1)