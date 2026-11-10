
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Header
)

from backend.order_processor import (
    process_order,
    find_alternatives
)

from fastapi.responses import Response
from pydantic import BaseModel
from backend.tts_service import generate_speech

from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, func
from datetime import datetime
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from backend.database import Base, engine, get_db
from backend.models import Product, Order, OrderItem
from backend.schemas import ProductCreate, StockUpdate
from backend.order_schemas import OrderCreate
from backend.order_processor import process_order
from backend.gnani_service import transcribe_audio
from backend.order_understanding import understand_order


# --------------------------------------------------
# DATABASE INITIALIZATION AND MIGRATION
# --------------------------------------------------

Base.metadata.create_all(bind=engine)

columns = [
    column["name"]
    for column in inspect(engine).get_columns("orders")
]

with engine.begin() as connection:

    if "idempotency_key" not in columns:
        connection.execute(
            text(
                "ALTER TABLE orders "
                "ADD COLUMN idempotency_key VARCHAR"
            )
        )

    connection.execute(
        text("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            uq_orders_idempotency_key
            ON orders (idempotency_key)
        """)
    )


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="DukaanSathi AI",
    description="Voice-powered smart kirana assistant",
    version="1.0"
)


# --------------------------------------------------
# HELPER: CHECK WHETHER TWO ORDER REQUESTS MATCH
# --------------------------------------------------

def order_matches(existing_order, order_data):

    if existing_order.customer_name != order_data.customer_name.strip():
        return False

    existing_items = sorted(
        [
            (
                item.product_name.lower(),
                float(item.quantity),
                item.unit.lower()
            )
            for item in existing_order.items
        ]
    )

    requested_items = sorted(
        [
            (
                item.product.strip().lower(),
                float(item.quantity),
                item.unit.strip().lower()
            )
            for item in order_data.items
        ]
    )

    return existing_items == requested_items


# --------------------------------------------------
# HELPER: FORMAT EXISTING ORDER RESPONSE
# --------------------------------------------------

def format_order_response(order, duplicate=False):

    return {
        "message": (
            "Duplicate request detected. Existing order returned."
            if duplicate
            else "Order created successfully"
        ),
        "order_id": order.id,
        "customer_name": order.customer_name,
        "items": [
            {
                "product": item.product_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "subtotal": item.subtotal
            }
            for item in order.items
        ],
        "total_amount": order.total_amount,
        "duplicate": duplicate
    }


# --------------------------------------------------
# HELPER: CREATE ORDER
# --------------------------------------------------

def create_order(
    order_data: OrderCreate,
    db: Session,
    idempotency_key: str = None
):

    try:

        customer_name = order_data.customer_name.strip()

        if not customer_name:
            raise HTTPException(
                status_code=400,
                detail="Customer name is required"
            )

        # Check for an already processed request
        if idempotency_key:

            existing_order = (
                db.query(Order)
                .filter(
                    Order.idempotency_key == idempotency_key
                )
                .first()
            )

            if existing_order:

                if not order_matches(existing_order, order_data):
                    raise HTTPException(
                        status_code=409,
                        detail="This request ID was already used for a different order."
                    )

                return format_order_response(
                    existing_order,
                    duplicate=True
                )

        processed_items = []
        total_amount = 0

        # Validate all items before deducting stock
        for item in order_data.items:

            product_name = item.product.strip()

            product = (
                db.query(Product)
                .filter(
                    Product.name.ilike(product_name)
                )
                .with_for_update()
                .first()
            )

            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"{product_name} not found"
                )

            if product.unit.lower() != item.unit.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"Unit mismatch for {product.name}. Available unit: {product.unit}"
                )

            if product.quantity < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product.name}. Available: {product.quantity}"
                )

            subtotal = round(
                product.price * item.quantity,
                2
            )

            processed_items.append({
                "product": product,
                "quantity": item.quantity,
                "subtotal": subtotal
            })

            total_amount += subtotal

        total_amount = round(total_amount, 2)

        # Create order
        new_order = Order(
            customer_name=customer_name,
            total_amount=total_amount,
            idempotency_key=idempotency_key
        )

        db.add(new_order)
        db.flush()

        # Deduct stock and save order items
        for entry in processed_items:

            product = entry["product"]
            quantity = entry["quantity"]
            subtotal = entry["subtotal"]

            product.quantity -= quantity

            new_item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=quantity,
                unit=product.unit,
                price=product.price,
                subtotal=subtotal
            )

            db.add(new_item)

        db.commit()
        db.refresh(new_order)

        return format_order_response(new_order)

    except IntegrityError:

        db.rollback()

        # Another simultaneous request may have created this order
        if idempotency_key:

            existing_order = (
                db.query(Order)
                .filter(
                    Order.idempotency_key == idempotency_key
                )
                .first()
            )

            if existing_order:

                if not order_matches(existing_order, order_data):
                    raise HTTPException(
                        status_code=409,
                        detail="This request ID was already used for a different order."
                    )

                return format_order_response(
                    existing_order,
                    duplicate=True
                )

        raise HTTPException(
            status_code=409,
            detail="Order could not be created because of a database conflict."
        )

    except HTTPException:

        db.rollback()
        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Order creation failed"
        )


# --------------------------------------------------
# HELPER: VALIDATE AUDIO FORMAT
# --------------------------------------------------

def validate_audio(audio):

    allowed_formats = {
        "audio/wav",
        "audio/mpeg",
        "audio/ogg",
        "audio/flac",
        "audio/aac",
        "audio/mp4",
        "audio/x-m4a"
    }

    if audio.content_type not in allowed_formats:

        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format"
        )


# --------------------------------------------------
# HELPER: PROCESS VOICE AND PREVIEW ORDER
# --------------------------------------------------

def generate_order_preview(audio, db):

    # Step 1: Speech recognition
    transcripts = transcribe_audio(audio)

    # Step 2: Understand order
    understood = understand_order(transcripts)

    if not understood["success"]:
        return {
            "status": "clarification_required",
            "message": understood["message"],
            "transcripts": transcripts
        }

    # Step 3: Check inventory
    unavailable_items = []

    for item_index, item in enumerate(understood["items"]):

        product = (
            db.query(Product)
            .filter(Product.name.ilike(item["product"]))
            .first()
        )

        # Product does not exist
        if not product:
            unavailable_items.append({
                "item_index": item_index,
                "requested_product": item["product"],
                "requested_quantity": item["quantity"],
                "unit": item["unit"],
                "available_stock": 0,
                "reason": "Product not found in inventory",
                "suggestions": []
            })
            continue

        # Check unit
        if product.unit.lower() != item["unit"].lower():
            return {
                "status": "clarification_required",
                "message": (
                    f"Unit mismatch for {product.name}. "
                    f"Available unit: {product.unit}"
                ),
                "transcripts": transcripts
            }

        # Check stock
        if product.quantity < item["quantity"]:

            alternatives = find_alternatives(
    product_name=product.name,
    db=db,
    category=product.category,
    unit=product.unit,
    required_quantity=item["quantity"]
)

            unavailable_items.append({
                "item_index": item_index,
                "requested_product": product.name,
                "requested_quantity": item["quantity"],
                "unit": product.unit,
                "available_stock": product.quantity,
                "reason": "Insufficient stock",
                "suggestions": alternatives.get("suggestions", [])
            })

    # Step 4: Ask for alternatives
    if unavailable_items:
        return {
            "status": "alternative_required",
            "requested_items": understood["items"],
            "customer_name": understood["customer_name"],
            "unavailable_items": unavailable_items,
            "transcripts": transcripts,
            "message": (
                "Some requested products are unavailable "
                "or have insufficient stock. Please select "
                "an alternative product."
            )
        }

    # Step 5: Generate normal bill preview
    preview = process_order(
        understood["items"],
        db
    )

    return {
        "status": "confirmation_required",
        "customer_name": understood["customer_name"],
        "items": preview["items"],
        "total_amount": preview["total_amount"],
        "transcripts": transcripts,
        "message": "Please confirm this order before billing."
    }
# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():

    return {
        "message": "Welcome to DukaanSathi AI!",
        "status": "Running"
    }


# --------------------------------------------------
# ADD PRODUCT
# --------------------------------------------------

@app.post("/products")
def add_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(Product)
        .filter(
            Product.name.ilike(product.name.strip())
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail="Product already exists"
        )

    new_product = Product(
        name=product.name.strip().title(),
        category=product.category,
        quantity=product.quantity,
        unit=product.unit,
        price=product.price,
        minimum_stock=product.minimum_stock
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "message": "Product added successfully",
        "product": new_product.name
    }


# --------------------------------------------------
# GET ALL PRODUCTS
# --------------------------------------------------

@app.get("/products")
def get_products(db: Session = Depends(get_db)):

    return db.query(Product).order_by(Product.name).all()


# --------------------------------------------------
# GET SINGLE PRODUCT
# --------------------------------------------------

@app.get("/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return product


# --------------------------------------------------
# UPDATE STOCK
# --------------------------------------------------

@app.patch("/products/{product_id}/stock")
def update_stock(
    product_id: int,
    update: StockUpdate,
    db: Session = Depends(get_db)
):

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product.quantity += update.quantity

    db.commit()
    db.refresh(product)

    return {
        "message": "Stock updated",
        "product": product.name,
        "available_quantity": product.quantity
    }


# --------------------------------------------------
# LOW STOCK
# --------------------------------------------------
@app.get("/inventory/low-stock")
def low_stock(db: Session = Depends(get_db)):

    products = (
        db.query(Product)
        .filter(
            Product.quantity <= Product.minimum_stock
        )
        .order_by(Product.quantity.asc())
        .all()
    )

    return {
        "total_alerts": len(products),
        "alerts": [
            {
                "product_id": product.id,
                "product": product.name,
                "category": product.category,
                "available_stock": product.quantity,
                "minimum_stock": product.minimum_stock,
                "unit": product.unit,
                "status": (
                    "Out of Stock"
                    if product.quantity == 0
                    else "Low Stock"
                )
            }
            for product in products
        ]
    }


# --------------------------------------------------
# ALTERNATIVE PRODUCT SUGGESTIONS
# --------------------------------------------------

@app.get("/inventory/suggestions/{product_name}")
def get_product_suggestions(
    product_name: str,
    category: str = None,
    unit: str = None,
    db: Session = Depends(get_db)
):

    return find_alternatives(
        product_name=product_name,
        db=db,
        category=category,
        unit=unit
    )


# --------------------------------------------------
# CREATE NORMAL ORDER
# --------------------------------------------------

@app.post("/orders")
def create_order_endpoint(
    order_data: OrderCreate,
    db: Session = Depends(get_db)
):

    return create_order(order_data, db)


# --------------------------------------------------
# GET ALL ORDERS
# --------------------------------------------------

@app.get("/orders")
def get_orders(db: Session = Depends(get_db)):

    return (
        db.query(Order)
        .order_by(Order.id.desc())
        .all()
    )


# --------------------------------------------------
# GET SINGLE ORDER
# --------------------------------------------------

@app.get("/orders/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db)
):

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return {
        "order_id": order.id,
        "customer_name": order.customer_name,
        "total_amount": order.total_amount,
        "created_at": order.created_at,
        "items": [
            {
                "product": item.product_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "price": item.price,
                "subtotal": item.subtotal
            }
            for item in order.items
        ]
    }


# --------------------------------------------------
# VOICE TRANSCRIPTION
# --------------------------------------------------

@app.post("/voice/transcribe")
def voice_transcription(
    audio: UploadFile = File(...)
):

    try:

        validate_audio(audio)

        transcripts = transcribe_audio(audio)

        return {
            "message": "Voice transcribed successfully",
            "transcript": transcripts,
            "language_mode": "Telugu + English"
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    finally:

        audio.file.close()


# --------------------------------------------------
# VOICE ORDER PREVIEW
# --------------------------------------------------

@app.post("/voice/preview-order")
def preview_voice_order(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    try:

        validate_audio(audio)

        return generate_order_preview(audio, db)

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Voice order preview failed"
        )

    finally:

        audio.file.close()


# --------------------------------------------------
# VOICE PROCESS ORDER
# This endpoint now previews instead of billing directly
# --------------------------------------------------

@app.post("/voice/process-order")
def process_voice_order(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    try:

        validate_audio(audio)

        return generate_order_preview(audio, db)

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Voice order processing failed"
        )

    finally:

        audio.file.close()

# --------------------------------------------------
# PREVIEW ORDER WITH APPROVED ALTERNATIVES
# --------------------------------------------------

@app.post("/voice/preview-substitution")
def preview_substitution(
    order_data: OrderCreate,
    db: Session = Depends(get_db)
):
    try:
        if not order_data.customer_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Customer name is required"
            )

        # Validate selected products and calculate the revised bill
        preview = process_order(
    [
        {
            "product": item.product,
            "quantity": item.quantity,
            "unit": item.unit
        }
        for item in order_data.items
    ],
    db
)

        return {
            "status": "confirmation_required",
            "customer_name": order_data.customer_name.strip(),
            "items": preview["items"],
            "total_amount": preview["total_amount"],
            "message": "Alternative accepted. Please confirm the updated order."
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Substitution preview failed"
        )

# --------------------------------------------------
# CONFIRM VOICE ORDER
# --------------------------------------------------

@app.post("/voice/confirm-order")
def confirm_voice_order(
    order_data: OrderCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key"
    ),
    db: Session = Depends(get_db)
):

    idempotency_key = idempotency_key.strip()

    if not idempotency_key:

        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key cannot be empty"
        )

    if len(idempotency_key) > 128:

        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key is too long"
        )

    return create_order(
        order_data,
        db,
        idempotency_key=idempotency_key
    )




class SpeechRequest(BaseModel):
    text: str
    language: str = "en-IN"


@app.post("/voice/speak")
def speak_text(request: SpeechRequest):
    try:
        audio = generate_speech(
            request.text,
            request.language
        )

        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=confirmation.wav"
            }
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))



@app.post("/voice/speak-order/{order_id}")
def speak_order_confirmation(order_id: int, db: Session = Depends(get_db)):

    # Fetch the actual saved order
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Build speech using saved order information
    item_details = []

    for item in order.items:
        quantity = f"{item.quantity:g}"

        item_details.append(
            f"{quantity} {item.unit} {item.product_name}"
        )

    items_text = ", ".join(item_details)
    total = f"{order.total_amount:g}"

    spoken_message = (
        f"నమస్కారం {order.customer_name} గారు. "
        f"మీ ఆర్డర్ కన్ఫర్మ్ అయింది. "
        f"{items_text}. "
        f"మొత్తం {total} రూపాయలు. "
        f"ధన్యవాదాలు!"
    )

    try:
        audio = generate_speech(
            spoken_message,
            language="auto"
        )

        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition":
                "inline; filename=order_confirmation.wav"
            }
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))





# --------------------------------------------------
# SALES ANALYTICS SUMMARY
# --------------------------------------------------

@app.get("/analytics/summary")
def sales_analytics_summary(
    period: str = "daily",
    db: Session = Depends(get_db)
):

    # Validate period
    if period not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=400,
            detail="Period must be daily, weekly or monthly"
        )

    # Use Indian Standard Time for dashboard dates
    ist = ZoneInfo("Asia/Kolkata")
    utc = ZoneInfo("UTC")

    now = datetime.now(ist)

    # Calculate date range
    if period == "daily":
        start_local = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    elif period == "weekly":
        start_local = (
            now.replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=6)
        )

    else:
        start_local = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

    # Convert local time to UTC for database comparison
    start_utc = (
        start_local.astimezone(utc).replace(tzinfo=None)
    )

    end_utc = now.astimezone(utc).replace(tzinfo=None)

    # Filter confirmed orders in the selected period
    orders_query = db.query(Order).filter(
        Order.created_at >= start_utc,
        Order.created_at <= end_utc
    )

    total_orders = orders_query.count()

    total_revenue = (
        orders_query.with_entities(
            func.coalesce(func.sum(Order.total_amount), 0)
        ).scalar()
    )

    average_order_value = (
        total_revenue / total_orders
        if total_orders > 0
        else 0
    )

    # Best-selling products
    top_products = (
        db.query(
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("total_quantity"),
            func.sum(OrderItem.subtotal).label("total_sales")
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            Order.created_at >= start_utc,
            Order.created_at <= end_utc
        )
        .group_by(OrderItem.product_name)
        .order_by(
            func.sum(OrderItem.quantity).desc()
        )
        .limit(5)
        .all()
    )

    return {
        "period": period,
        "date_from": start_local.isoformat(),
        "date_to": now.isoformat(),
        "total_revenue": round(float(total_revenue), 2),
        "total_orders": total_orders,
        "average_order_value": round(
            float(average_order_value), 2
        ),
        "top_products": [
            {
                "product": item.product_name,
                "quantity_sold": float(item.total_quantity),
                "total_sales": round(
                    float(item.total_sales), 2
                )
            }
            for item in top_products
        ]
    }


# --------------------------------------------------
# DAILY REVENUE TREND
# --------------------------------------------------

@app.get("/analytics/revenue-trend")
def revenue_trend(
    days: int = 7,
    db: Session = Depends(get_db)
):

    if days < 1 or days > 90:
        raise HTTPException(
            status_code=400,
            detail="Days must be between 1 and 90"
        )

    ist = ZoneInfo("Asia/Kolkata")
    utc = ZoneInfo("UTC")

    now = datetime.now(ist)

    # Start from midnight IST
    today = now.date()
    start_date = today - timedelta(days=days - 1)

    start_local = datetime.combine(
        start_date,
        datetime.min.time(),
        tzinfo=ist
    )

    start_utc = (
        start_local.astimezone(utc).replace(tzinfo=None)
    )

    end_utc = (
        now.astimezone(utc).replace(tzinfo=None)
    )

    # Fetch orders within the date range
    orders = (
        db.query(Order)
        .filter(
            Order.created_at >= start_utc,
            Order.created_at <= end_utc
        )
        .all()
    )

    # Initialize every day with zero revenue
    daily_sales = {}

    for i in range(days):
        current_date = start_date + timedelta(days=i)

        daily_sales[current_date.isoformat()] = {
            "date": current_date.isoformat(),
            "revenue": 0.0,
            "orders": 0
        }

    # Group orders by Indian local date
    for order in orders:

        created_at = order.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=utc)

        order_date = (
            created_at.astimezone(ist).date().isoformat()
        )

        if order_date in daily_sales:

            daily_sales[order_date]["revenue"] += (
                float(order.total_amount)
            )

            daily_sales[order_date]["orders"] += 1

    # Round revenue values
    for item in daily_sales.values():
        item["revenue"] = round(item["revenue"], 2)

    return {
        "period_days": days,
        "date_from": start_date.isoformat(),
        "date_to": today.isoformat(),
        "total_revenue": round(
            sum(item["revenue"] for item in daily_sales.values()),
            2
        ),
        "total_orders": sum(
            item["orders"] for item in daily_sales.values()
        ),
        "daily_sales": list(daily_sales.values())
    }


app.mount(
    "/app",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)