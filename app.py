import re
import os
from pathlib import Path
import secrets
import requests
from ai_engine import ask_ai
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_limiter import Limiter
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from security_config import configure_security

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

app = Flask(__name__)
app = configure_security(app)
limiter = Limiter(
    key_func=lambda: request.remote_addr,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "redis://127.0.0.1:6379/0")
)

configure_security(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agency.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, default="AI Agency Demo Business")
    owner_name = db.Column(db.String(120), default="")
    phone = db.Column(db.String(50), default="")
    email = db.Column(db.String(150), default="")
    created_at = db.Column(db.DateTime, default=db.func.now())


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500), default="")


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50), default="")
    message = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="New")


with app.app_context():
    db.create_all()




CSRF_COOKIE_NAME = "ai_agency_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        supplied = request.headers.get(CSRF_HEADER_NAME, "")
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")

        if not supplied or not cookie_token or supplied != cookie_token:
            return jsonify({"error": "CSRF validation failed"}), 403

@app.after_request
def csrf_cookie(response):
    if not request.cookies.get(CSRF_COOKIE_NAME):
        token = secrets.token_urlsafe(32)
        production = os.getenv("PRODUCTION", "0") == "1"

        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            httponly=False,
            secure=production,
            samesite="Lax",
            max_age=3600,
        )

    return response


# ===== AI AGENCY CUSTOMER PLATFORM =====

class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())


# ===== PAYMENT MODEL =====
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        nullable=True
    )
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(50), default="")
    plan = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    transaction_id = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    created_at = db.Column(db.DateTime, default=db.func.now())

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.get_json(silent=True) or request.form
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
    admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")

    from werkzeug.security import check_password_hash

    password_ok = False

    if admin_password_hash:
        try:
            password_ok = check_password_hash(
                admin_password_hash,
                password
            )
        except ValueError:
            password_ok = False

    if username == admin_username and password_ok:
        session.permanent = True
        session["admin_logged_in"] = True
        return jsonify({"message": "Login successful"})

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def require_admin():
    return session.get("admin_logged_in") is True


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "AI Agency"
    })




@app.route("/welcome", methods=["GET"])
def welcome():
    return render_template("welcome.html")

@app.route("/dashboard", methods=["GET"])
def dashboard():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    products = Product.query.filter_by(
        business_id=business.id
    ).count() if business else 0
    leads = Lead.query.filter_by(
        business_id=business.id
    ).count() if business else 0
    orders = Order.query.filter_by(
        business_id=business.id
    ).count() if business else 0

    pending_orders = Order.query.filter_by(
        business_id=business.id,
        status="Pending"
    ).count() if business else 0
    converted_leads = Lead.query.filter_by(
        business_id=business.id,
        status="Converted"
    ).count() if business else 0

    revenue = db.session.query(
        db.func.coalesce(db.func.sum(Order.amount), 0)
    ).filter(
        Order.business_id == business.id
    ).scalar() if business else 0

    return jsonify({
        "products": products,
        "leads": leads,
        "orders": orders,
        "revenue": float(revenue or 0),
        "pending_orders": pending_orders,
        "converted_leads": converted_leads
    })


@app.route("/products", methods=["GET"])
def products():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401

    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    products = Product.query.filter_by(
        business_id=business.id
    ).order_by(Product.id.desc()).all()

    return jsonify([
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description
        }
        for product in products
    ])


@app.route("/products", methods=["POST"])
def add_product():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json() or {}

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()

    try:
        price = float(data.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid price"}), 400

    if not name:
        return jsonify({"error": "Product name is required"}), 400

    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    product = Product(
        business_id=business.id,
        name=name,
        price=price,
        description=description
    )

    db.session.add(product)
    db.session.commit()

    return jsonify({
        "message": "Product created",
        "id": product.id
    }), 201



@app.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    product = Product.query.filter_by(
        id=product_id,
        business_id=business.id
    ).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    data = request.get_json() or {}

    name = str(data.get("name", product.name)).strip()
    description = str(data.get("description", product.description or "")).strip()

    try:
        price = float(data.get("price", product.price))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid price"}), 400

    if not name:
        return jsonify({"error": "Product name is required"}), 400

    product.name = name
    product.price = price
    product.description = description

    db.session.commit()

    return jsonify({
        "message": "Product updated",
        "id": product.id
    })


@app.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    product = Product.query.filter_by(
        id=product_id,
        business_id=business.id
    ).first()

    if not product:
        return jsonify({"error": "Product not found"}), 404

    db.session.delete(product)
    db.session.commit()

    return jsonify({
        "message": "Product deleted",
        "id": product_id
    })



class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(50), default="")
    customer_address = db.Column(db.String(300), default="")
    product_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(30), default="Pending")



@app.route("/orders", methods=["GET"])
def orders():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401

    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    orders = Order.query.filter_by(
        business_id=business.id
    ).order_by(Order.id.desc()).all()

    return jsonify([
        {
            "id": order.id,
            "customer_name": order.customer_name,
            "customer_phone": getattr(order, "customer_phone", ""),
            "customer_address": getattr(order, "customer_address", ""),
            "product_name": order.product_name,
            "quantity": order.quantity,
            "amount": order.amount,
            "status": order.status
        }
        for order in orders
    ])



@app.route("/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    order = Order.query.filter_by(
        id=order_id,
        business_id=business.id
    ).first()

    if not order:
        return jsonify({"error": "Order not found"}), 404

    data = request.get_json() or {}
    status = str(data.get("status", order.status)).strip()

    allowed = ["Pending", "Processing", "Completed", "Cancelled"]

    if status not in allowed:
        return jsonify({"error": "Invalid order status"}), 400

    order.status = status
    db.session.commit()

    return jsonify({
        "message": "Order status updated",
        "id": order.id,
        "status": order.status
    })


@app.route("/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    order = Order.query.filter_by(
        id=order_id,
        business_id=business.id
    ).first()

    if not order:
        return jsonify({"error": "Order not found"}), 404

    db.session.delete(order)
    db.session.commit()

    return jsonify({
        "message": "Order deleted",
        "id": order_id
    })


@app.route("/orders", methods=["POST"])
def add_order():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json() or {}

    customer_name = str(data.get("customer_name", "")).strip()
    customer_phone = str(data.get("customer_phone", "")).strip()
    customer_address = str(data.get("customer_address", "")).strip()
    product_name = str(data.get("product_name", "")).strip()

    try:
        quantity = int(data.get("quantity", 1))
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid quantity or amount"}), 400

    if not customer_name or not product_name:
        return jsonify({
            "error": "Customer name and product name are required"
        }), 400

    if quantity < 1 or amount < 0:
        return jsonify({
            "error": "Invalid quantity or amount"
        }), 400

    order = Order(
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        product_name=product_name,
        quantity=quantity,
        amount=amount,
        status="Pending"
    )

    db.session.add(order)
    db.session.commit()

    return jsonify({
        "message": "Order created",
        "id": order.id
    }), 201


@app.route("/leads", methods=["GET"])
def leads():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401

    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    leads = Lead.query.filter_by(
        business_id=business.id
    ).order_by(Lead.id.desc()).all()

    return jsonify([
        {
            "id": lead.id,
            "name": lead.name,
            "phone": lead.phone,
            "message": lead.message,
            "status": lead.status
        }
        for lead in leads
    ])


@app.route("/leads", methods=["POST"])
def add_lead():
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json() or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400

    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    lead = Lead(
        business_id=business.id,
        name=name,
        phone=phone,
        message=message
    )

    db.session.add(lead)
    db.session.commit()

    return jsonify({
        "message": "Lead created",
        "id": lead.id
    }), 201



@app.route("/leads/<int:lead_id>", methods=["PUT"])
def update_lead(lead_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    lead = Lead.query.filter_by(
        id=lead_id,
        business_id=business.id
    ).first()

    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json() or {}

    status = str(data.get("status", lead.status)).strip()

    allowed = ["New", "Contacted", "Converted"]

    if status not in allowed:
        return jsonify({
            "error": "Invalid status"
        }), 400

    lead.status = status
    db.session.commit()

    return jsonify({
        "message": "Lead status updated",
        "id": lead.id,
        "status": lead.status
    })


@app.route("/leads/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    if not require_admin():
        return jsonify({"error": "Authentication required"}), 401
    business = require_active_business()
    if business is None:
        return jsonify({"error": "No active business"}), 400

    lead = Lead.query.filter_by(
        id=lead_id,
        business_id=business.id
    ).first()

    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    db.session.delete(lead)
    db.session.commit()

    return jsonify({
        "message": "Lead deleted",
        "id": lead_id
    })


@app.route("/chat", methods=["POST"])
def chat():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    try:
        reply = ask_ai(message)
        return jsonify({
            "message": message,
            "reply": reply,
            "ai_status": "online"
        })
    except Exception as exc:
        error_text = str(exc)

        # API credits/quota unavailable: keep application healthy.
        if (
            "credit_balance_exhausted" in error_text
            or "insufficient_quota" in error_text
            or "429" in error_text
        ):
            return jsonify({
                "message": message,
                "reply": "AI service is temporarily unavailable because API credits are exhausted. Please try again after API credits are added.",
                "ai_status": "temporarily_unavailable"
            }), 503

        return jsonify({
            "error": "AI service temporarily unavailable",
            "ai_status": "error"
        }), 503

@app.route("/api/ai-insights", methods=["GET"])
def ai_business_insights():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    business = require_active_business()
    if business is None:
        products = []
    else:
        products = Product.query.filter_by(
            business_id=business.id
        ).all()
    business = require_active_business()
    if business is None:
        leads = []
    else:
        leads = Lead.query.filter_by(
            business_id=business.id
        ).all()
    business = require_active_business()
    if business is None:
        orders = []
    else:
        orders = Order.query.filter_by(
            business_id=business.id
        ).all()

    total_revenue = sum(float(o.amount or 0) for o in orders)
    pending_orders = sum(1 for o in orders if o.status == "Pending")
    processing_orders = sum(1 for o in orders if o.status == "Processing")
    completed_orders = sum(1 for o in orders if o.status == "Completed")
    cancelled_orders = sum(1 for o in orders if o.status == "Cancelled")

    converted_leads = sum(
        1 for lead in leads
        if str(lead.status).lower() in ("converted", "customer")
    )

    product_sales = {}
    for order in orders:
        name = order.product_name or "Unknown"
        product_sales[name] = product_sales.get(name, 0) + int(order.quantity or 0)

    top_product = None
    if product_sales:
        top_product = max(product_sales, key=product_sales.get)

    insights = []
    recommendations = []

    if pending_orders:
        insights.append(
            f"You have {pending_orders} pending order(s) that need attention."
        )
        recommendations.append(
            "Review pending orders and contact customers to confirm delivery details."
        )

    if processing_orders:
        insights.append(
            f"{processing_orders} order(s) are currently being processed."
        )

    if completed_orders:
        insights.append(
            f"{completed_orders} order(s) have been completed."
        )

    if cancelled_orders:
        insights.append(
            f"{cancelled_orders} order(s) have been cancelled."
        )

    if top_product:
        insights.append(
            f"Your most ordered product is {top_product}."
        )
        recommendations.append(
            f"Consider promoting {top_product} because it currently has the highest order quantity."
        )

    if leads and converted_leads:
        insights.append(
            f"{converted_leads} lead(s) are marked as converted."
        )

    if leads and not converted_leads:
        recommendations.append(
            "Follow up with your leads and update their status when they become customers."
        )

    if not products:
        recommendations.append(
            "Add your main products so customers can discover and order them."
        )

    if not insights:
        insights.append(
            "Your AI business assistant is ready. Add products, leads and orders to generate insights."
        )

    if not recommendations:
        recommendations.append(
            "Keep your products, leads and orders updated for better business insights."
        )

    return jsonify({
        "status": "success",
        "summary": {
            "products": len(products),
            "leads": len(leads),
            "orders": len(orders),
            "revenue": total_revenue,
            "pending_orders": pending_orders,
            "processing_orders": processing_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "converted_leads": converted_leads,
            "top_product": top_product
        },
        "insights": insights,
        "recommendations": recommendations
    })


@app.route("/api/ai-followups", methods=["GET"])
def ai_followups():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    followups = []

    # Pending order follow-ups
    business = require_active_business()
    if business is None:
        return jsonify({
            "status": "success",
            "followups": [],
            "total": 0
        })

    pending_orders = Order.query.filter_by(
        business_id=business.id,
        status="Pending"
    ).order_by(
        Order.id.desc()
    ).all()

    for order in pending_orders:
        customer = order.customer_name or "Customer"
        phone = order.customer_phone or ""
        address = order.customer_address or ""

        message = (
            f"Assalam-o-Alaikum {customer}, "
            f"your order #{order.id} for {order.product_name} "
            f"(Qty {order.quantity}, Rs {order.amount:g}) has been received. "
            f"We are confirming your order and delivery details."
        )

        followups.append({
            "type": "Order Follow-up",
            "icon": "📦",
            "customer": customer,
            "phone": phone,
            "order_id": order.id,
            "message": message,
            "reason": "Pending order needs confirmation."
        })

    # Lead follow-ups
    business = require_active_business()
    if business is None:
        return jsonify([])

    leads = Lead.query.filter_by(
        business_id=business.id
    ).order_by(Lead.id.desc()).all()

    for lead in leads:
        status = str(lead.status or "New").lower()

        if status not in ("converted", "customer"):
            customer = lead.name or "Customer"
            phone = lead.phone or ""
            requirement = lead.message or "your requirement"

            message = (
                f"Assalam-o-Alaikum {customer}, "
                f"thank you for contacting us. "
                f"We are following up regarding {requirement}. "
                f"Please let us know if you would like more information or "
                f"would like to place an order."
            )

            followups.append({
                "type": "Lead Follow-up",
                "icon": "👥",
                "customer": customer,
                "phone": phone,
                "order_id": None,
                "message": message,
                "reason": "Lead has not been converted yet."
            })

    return jsonify({
        "status": "success",
        "total": len(followups),
        "followups": followups
    })



def get_active_business():
    business_id = session.get("active_business_id")

    if business_id:
        return db.session.get(Business, int(business_id))

    return Business.query.order_by(Business.id.asc()).first()


def active_business_or_error():
    business = require_active_business()
    if business is None:
        return None, (jsonify({"error": "No active business"}), 400)
    return business, None

def require_active_business():
    business = get_active_business()

    if business is None:
        return None

    session["active_business_id"] = business.id
    session["active_business_name"] = business.name

    return business


@app.route("/api/businesses", methods=["GET", "POST"])
def api_businesses():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "GET":
        businesses = Business.query.order_by(Business.id.asc()).all()

        return jsonify({
            "status": "success",
            "businesses": [
                {
                    "id": b.id,
                    "name": b.name,
                    "owner_name": b.owner_name or "",
                    "phone": b.phone or "",
                    "email": b.email or ""
                }
                for b in businesses
            ]
        })

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    owner_name = str(data.get("owner_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()

    if not name:
        return jsonify({
            "error": "Business name is required."
        }), 400

    business = Business(
        name=name,
        owner_name=owner_name,
        phone=phone,
        email=email
    )

    db.session.add(business)
    db.session.commit()

    return jsonify({
        "status": "success",
        "business": {
            "id": business.id,
            "name": business.name,
            "owner_name": business.owner_name or "",
            "phone": business.phone or "",
            "email": business.email or ""
        }
    }), 201


@app.route("/api/businesses/<int:business_id>", methods=["GET"])
def api_business_details(business_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    business = db.session.get(Business, business_id)

    if business is None:
        return jsonify({"error": "Business not found."}), 404

    return jsonify({
        "status": "success",
        "business": {
            "id": business.id,
            "name": business.name,
            "owner_name": business.owner_name or "",
            "phone": business.phone or "",
            "email": business.email or ""
        }
    })


@app.route("/api/businesses/activate/<int:business_id>", methods=["POST"])
def activate_business(business_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    business = db.session.get(Business, business_id)

    if business is None:
        return jsonify({"error": "Business not found."}), 404

    session["active_business_id"] = business.id
    session["active_business_name"] = business.name

    return jsonify({
        "status": "success",
        "active_business": {
            "id": business.id,
            "name": business.name
        }
    })


# ===== CUSTOMER ACCOUNT ROUTES =====

@app.route("/signup", methods=["GET", "POST"])
def customer_signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.get_json(silent=True) or request.form
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or len(password) < 8:
        return jsonify({
            "error": "Name, email and password (minimum 8 characters) are required."
        }), 400

    existing = Customer.query.filter_by(email=email).first()
    if existing:
        return jsonify({"error": "Account already exists."}), 409

    from werkzeug.security import generate_password_hash

    business = Business(
        name=f"{name}'s Business",
        owner_name=name,
        email=email,
    )
    db.session.add(business)
    db.session.flush()

    customer = Customer(
        business_id=business.id,
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(customer)
    db.session.commit()

    session["customer_id"] = customer.id
    session["customer_name"] = customer.name
    session["customer_business_id"] = business.id

    if request.is_json:
        return jsonify({
            "message": "Account created successfully",
            "redirect": "/customer-dashboard"
        }), 201

    return redirect(url_for("customer_dashboard"))


@app.route("/customer-login", methods=["GET", "POST"])
def customer_login():
    if request.method == "GET":
        return render_template("customer_login.html")

    data = request.get_json(silent=True) or request.form
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    customer = Customer.query.filter_by(email=email).first()

    from werkzeug.security import check_password_hash

    if not customer or not check_password_hash(customer.password_hash, password):
        if request.is_json:
            return jsonify({"error": "Invalid email or password"}), 401
        return render_template(
            "customer_login.html",
            error="Invalid email or password"
        ), 401

    session["customer_id"] = customer.id
    session["customer_name"] = customer.name
    session["customer_business_id"] = customer.business_id

    if request.is_json:
        return jsonify({
            "message": "Login successful",
            "redirect": "/customer-dashboard"
        })

    return redirect(url_for("customer_dashboard"))


@app.route("/customer-dashboard", methods=["GET"])
def customer_dashboard():
    customer_id = session.get("customer_id")

    if not customer_id:
        return redirect(url_for("customer_login"))

    customer = db.session.get(Customer, int(customer_id))

    if customer is None:
        session.pop("customer_id", None)
        session.pop("customer_name", None)
        session.pop("customer_business_id", None)
        return redirect(url_for("customer_login"))

    business_id = customer.business_id
    business = db.session.get(Business, business_id) if business_id else None

    product_count = (
        Product.query.filter_by(business_id=business_id).count()
        if business_id else 0
    )

    lead_count = (
        Lead.query.filter_by(business_id=business_id).count()
        if business_id else 0
    )

    order_count = (
        Order.query.filter_by(business_id=business_id).count()
        if business_id else 0
    )

    pending_orders = (
        Order.query.filter_by(
            business_id=business_id,
            status="Pending"
        ).count()
        if business_id else 0
    )

    return render_template(
        "customer_dashboard.html",
        customer=customer,
        business=business,
        product_count=product_count,
        lead_count=lead_count,
        order_count=order_count,
        pending_orders=pending_orders,
    )


@app.route("/customer-logout", methods=["GET", "POST"])
def customer_logout():
    session.pop("customer_id", None)
    session.pop("customer_name", None)
    session.pop("customer_business_id", None)

    if request.is_json:
        return jsonify({"message": "Logged out"})

    return redirect(url_for("customer_login"))



# ===== AI AGENCY PWA ROUTE =====

@app.route("/service-worker.js")
def service_worker():
    sw = Path("static/sw.js").read_text()
    return sw, 200, {"Content-Type": "application/javascript"}

# ===== AI AGENCY PROFESSIONAL PAGES =====

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/services")
def services():
    return render_template("services.html")


# ===== AI AGENCY PRICING PAGE =====

@app.route("/pricing")
def pricing():
    return render_template("pricing.html")


# ===== AI AGENCY CUSTOMER SIGNUP UI =====

@app.route("/signup", methods=["GET"])
def signup():
    return render_template("signup.html")






# ===== PUBLIC PAYMENT PAGE =====
@app.route("/payment", methods=["GET"])
def payment():
    return render_template("payment.html")



# ===== PUBLIC LEGAL PAGE =====
@app.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")



# ===== PUBLIC LEGAL PAGE =====
@app.route("/terms", methods=["GET"])
def terms():
    return render_template("terms.html")



# ===== PUBLIC LEGAL PAGE =====
@app.route("/refund-policy", methods=["GET"])
def refund_policy():
    return render_template("refund_policy.html")


# ===== PAYMENT SUBMISSION =====
@app.route("/payment/submit", methods=["POST"])
@limiter.limit("10 per hour")
def payment_submit():
    data = request.get_json(silent=True) or request.form

    customer_name = str(data.get("customer_name", "")).strip()
    customer_phone = str(data.get("customer_phone", "")).strip()
    plan = str(data.get("plan", "")).strip()
    transaction_id = str(data.get("transaction_id", "")).strip()

    plans = {
        "Starter": 10000,
        "Business": 25000,
        "Pro": 50000,
    }

    if not customer_name or not plan or not transaction_id:
        return jsonify({"error": "Required payment fields are missing"}), 400

    if plan not in plans:
        return jsonify({"error": "Invalid plan"}), 400

    payment = Payment(
        business_id=get_active_business().id if get_active_business() else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        plan=plan,
        amount=plans[plan],
        transaction_id=transaction_id,
        status="Pending",
    )

    db.session.add(payment)
    db.session.commit()

    return jsonify({
        "message": "Payment submitted for verification",
        "payment_id": payment.id,
        "status": payment.status,
    }), 201


# ===== ADMIN PAYMENTS =====
@app.route("/admin/payments", methods=["GET"])
def admin_payments():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    payments = Payment.query.order_by(Payment.id.desc()).all()

    return jsonify([
        {
            "id": p.id,
            "customer_name": p.customer_name,
            "customer_phone": p.customer_phone,
            "plan": p.plan,
            "amount": p.amount,
            "transaction_id": p.transaction_id,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ])


@app.route("/admin/payments/<int:payment_id>/status", methods=["POST"])
def admin_payment_status(payment_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form
    status = str(data.get("status", "")).strip()

    allowed = {"Pending", "Verified", "Rejected"}

    if status not in allowed:
        return jsonify({"error": "Invalid status"}), 400

    payment = db.session.get(Payment, payment_id)

    if payment is None:
        return jsonify({"error": "Payment not found"}), 404

    payment.status = status
    db.session.commit()

    return jsonify({
        "message": "Payment status updated",
        "payment_id": payment.id,
        "status": payment.status,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


# ===== PUBLIC BUSINESS INQUIRY / CONTACT =====
@app.route("/contact", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def contact():
    if request.method == "GET":
        return render_template("contact.html")

    data = request.get_json(silent=True) or request.form

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name or not message:
        return jsonify({
            "error": "Name and business requirement are required."
        }), 400

    if len(name) > 120 or len(phone) > 50 or len(message) > 500:
        return jsonify({"error": "Input is too long."}), 400

    lead = Lead(
        name=name,
        phone=phone,
        message=message,
        status="New"
    )

    db.session.add(lead)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Your business inquiry has been received."
    }), 201


@app.route("/privacy", methods=["GET"])
def privacy_page_public():
    return render_template("privacy.html")


@app.route("/terms", methods=["GET"])
def terms_page_public():
    return render_template("terms.html")


@app.route("/refund-policy", methods=["GET"])
def refund_policy_page_public():
    return render_template("refund_policy.html")
