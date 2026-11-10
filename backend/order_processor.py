from sqlalchemy.orm import Session
from backend.models import Product


def process_order(items: list, db: Session):

    processed_items = []
    total_amount = 0

    for item in items:

        product_name = item["product"].strip()
        quantity = float(item["quantity"])
        requested_unit = item["unit"].strip().lower()

        if quantity <= 0:
            raise ValueError(
                f"Invalid quantity for {product_name}"
            )

        product = db.query(Product).filter(
            Product.name.ilike(product_name)
        ).first()

        if not product:
            raise ValueError(
                f"{product_name} is not available in inventory"
            )

        if product.unit.lower() != requested_unit:
            raise ValueError(
                f"Unit mismatch for {product.name}. "
                f"Available unit: {product.unit}"
            )

        if product.quantity < quantity:
            raise ValueError(
                f"Insufficient stock for {product.name}. "
                f"Available: {product.quantity} {product.unit}"
            )

        subtotal = round(product.price * quantity, 2)

        processed_items.append({
            "product": product.name,
            "quantity": quantity,
            "unit": product.unit,
            "price": product.price,
            "subtotal": subtotal
        })

        total_amount += subtotal

    return {
        "items": processed_items,
        "total_amount": round(total_amount, 2)
    }

def find_alternatives(
    product_name,
    db,
    category=None,
    unit=None,
    required_quantity=None
):
    product = db.query(Product).filter(
        Product.name.ilike(product_name)
    ).first()

    if product:
        category = category or product.category
        unit = unit or product.unit

    query = db.query(Product).filter(
        Product.name.ilike(f"%{product_name}%") == False,
        Product.quantity > 0
    )

    if category:
        query = query.filter(Product.category == category)

    if unit:
        query = query.filter(Product.unit.ilike(unit))

    # Only suggest products with sufficient stock
    if required_quantity is not None:
        query = query.filter(
            Product.quantity >= required_quantity
        )

    alternatives = query.order_by(
        Product.quantity.desc()
    ).limit(5).all()

    return {
        "suggestions": [
            {
                "product_id": item.id,
                "product": item.name,
                "category": item.category,
                "available_stock": item.quantity,
                "unit": item.unit,
                "price": item.price
            }
            for item in alternatives
        ]
    }
    # Check whether the requested product exists
    requested_product = (
        db.query(Product)
        .filter(Product.name.ilike(product_name.strip()))
        .first()
    )

    # Automatically identify category and unit when possible
    if requested_product:
        category = requested_product.category
        unit = unit or requested_product.unit

    # Cannot reliably suggest alternatives without a category
    if not category:
        return {
            "requested_product": product_name,
            "suggestions": [],
            "message": "Please specify the product category."
        }

    # Find available products in the same category
    query = db.query(Product).filter(
        Product.category.ilike(category.strip()),
        Product.quantity > 0,
        Product.name.notilike(product_name.strip())
    )

    # Prefer alternatives with the same unit
    if unit:
        query = query.filter(
            Product.unit.ilike(unit.strip())
        )

    alternatives = query.order_by(
        Product.quantity.desc()
    ).limit(5).all()

    suggestions = [
        {
            "product_id": product.id,
            "product": product.name,
            "category": product.category,
            "available_stock": product.quantity,
            "unit": product.unit,
            "price": product.price
        }
        for product in alternatives
    ]

    return {
        "requested_product": product_name,
        "category": category,
        "suggestions": suggestions,
        "message": (
            "Alternative products found."
            if suggestions
            else "No suitable alternatives available."
        )
    }
