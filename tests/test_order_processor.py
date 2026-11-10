from backend.order_processor import process_order

# This test will use your actual database session
from backend.database import SessionLocal

db = SessionLocal()

try:
    order = process_order(
        [
            {
                "product": "Rice",
                "quantity": 2,
                "unit": "kg"
            },
            {
                "product": "Sunflower Oil",
                "quantity": 1,
                "unit": "litre"
            }
        ],
        db
    )

    print(order)

finally:
    db.close()