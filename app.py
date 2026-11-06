from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime
import os, re

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///sportix.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SPORTIX_SECRET_KEY", "change-this-secret-before-deployment")
db = SQLAlchemy(app)

CATEGORIES = [
    "Cricket Equipment", "Football Equipment", "Basketball Equipment",
    "Fitness & Gym Accessories", "Running Shoes", "Sports Apparel",
    "Outdoor Sports Equipment"
]

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), nullable=False, index=True)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(500), nullable=False)
    brand = db.Column(db.String(60), nullable=False, default="SPORTIX")
    rating = db.Column(db.Float, nullable=False, default=4.5)
    reviews = db.Column(db.Integer, nullable=False, default=20)
    stock = db.Column(db.Integer, nullable=False, default=25)

    def as_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category,
                "price": self.price, "description": self.description, "image": self.image,
                "brand": self.brand, "rating": self.rating, "reviews": self.reviews,
                "stock": self.stock}

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False, default="Cash on Delivery")
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Placed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(140), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

SEED = [
    ("SS Ton Cricket Bat", "Cricket Equipment", 6499, "A balanced English-willow style bat built for confident shots and practice sessions.", "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=900&q=85", "SS", 4.8, 34),
    ("Adidas Football (Size 5)", "Football Equipment", 1999, "Durable training football with a dependable touch for matches and practice.", "https://images.unsplash.com/photo-1614632537423-1e6c2e7e0c4e?auto=format&fit=crop&w=900&q=85", "Adidas", 4.6, 18),
    ("Adjustable Dumbbell Set", "Fitness & Gym Accessories", 5999, "Versatile strength-training set for home workouts and progressive training.", "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?auto=format&fit=crop&w=900&q=85", "ProFit", 4.7, 22),
    ("Nike Revolution 7", "Running Shoes", 4499, "Lightweight everyday running shoes with a cushioned ride and breathable upper.", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85", "Nike", 4.7, 27),
    ("Basketball Pro Series", "Basketball Equipment", 1499, "Grip-textured basketball designed for indoor and outdoor court sessions.", "https://images.unsplash.com/photo-1519861531473-9200262188bf?auto=format&fit=crop&w=900&q=85", "Spalding", 4.5, 16),
    ("Goalkeeper Gloves", "Football Equipment", 1499, "Secure wrist support and grippy palms for training and match-day saves.", "https://images.unsplash.com/photo-1521412644187-c49fa049e84d?auto=format&fit=crop&w=900&q=85", "Vector X", 4.4, 11),
    ("Performance Training T-shirt", "Sports Apparel", 899, "Sweat-wicking comfort and a flexible fit for workouts and outdoor activity.", "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85", "SPORTIX", 4.3, 13),
    ("Trail Sports Backpack", "Outdoor Sports Equipment", 2299, "A practical, lightweight pack for day hikes, travel and outdoor training.", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85", "Wildcraft", 4.6, 19),
    ("Shin Guards", "Football Equipment", 899, "Lightweight protective shin guards designed for comfortable movement.", "https://images.unsplash.com/photo-1517466787929-bc90951d0974?auto=format&fit=crop&w=900&q=85", "Nike", 4.4, 9),
    ("Training Cones Set", "Outdoor Sports Equipment", 499, "Bright, durable cones for agility drills, team practice and fitness circuits.", "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=900&q=85", "SPORTIX", 4.5, 8),
    ("Resistance Bands Kit", "Fitness & Gym Accessories", 799, "Multiple resistance levels for mobility, strength work and warm-ups.", "https://images.unsplash.com/photo-1598289431512-b97b0917affc?auto=format&fit=crop&w=900&q=85", "ProFit", 4.6, 21),
    ("Court Classic Jersey", "Sports Apparel", 1299, "A relaxed, breathable jersey inspired by classic team-sport style.", "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=900&q=85", "SPORTIX", 4.2, 7),
    ("Cricket Training Stumps", "Cricket Equipment", 1199, "Portable stumps set for net practice, coaching and backyard games.", "https://images.unsplash.com/photo-1593766827228-8737b1cd1474?auto=format&fit=crop&w=900&q=85", "SG", 4.3, 12),
    ("Everyday Sports Socks", "Running Shoes", 399, "Comfortable, supportive socks for daily runs and gym sessions.", "https://images.unsplash.com/photo-1586350977771-b3b0afd6d1e6?auto=format&fit=crop&w=900&q=85", "SPORTIX", 4.1, 6),
]

def seed_products():
    if Product.query.count() == 0:
        for name, category, price, desc, image, brand, rating, reviews in SEED:
            db.session.add(Product(name=name, category=category, price=price, description=desc,
                                   image=image, brand=brand, rating=rating, reviews=reviews))
        db.session.commit()

with app.app_context():
    db.create_all()
    seed_products()

@app.get("/")
def home():
    featured = Product.query.order_by(Product.rating.desc()).limit(8).all()
    return render_template("index.html", categories=CATEGORIES, featured=featured)

@app.get("/shop")
def shop():
    return render_template("shop.html", categories=CATEGORIES)

@app.get("/api/products")
def api_products():
    query = Product.query
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    brand = request.args.get("brand", "").strip()
    sort = request.args.get("sort", "featured")
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like),
                                 Product.brand.ilike(like), Product.category.ilike(like)))
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if brand:
        query = query.filter_by(brand=brand)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if sort == "price_low":
        query = query.order_by(Product.price.asc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc())
    elif sort == "rating":
        query = query.order_by(Product.rating.desc())
    else:
        query = query.order_by(Product.id.asc())
    products = query.all()
    return jsonify({"products": [p.as_dict() for p in products], "count": len(products),
                    "brands": sorted({p.brand for p in Product.query.all()})})

@app.get("/api/products/<int:product_id>")
def api_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    return jsonify(product.as_dict())

@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    required = ["customer_name", "email", "phone", "address", "city", "pincode", "items"]
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Please complete all required fields and add items to your cart."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not re.match(r"^[0-9]{6}$", str(data["pincode"])):
        return jsonify({"error": "Enter a valid 6-digit PIN code."}), 400
    if not re.match(r"^[0-9+\-\s]{10,15}$", str(data["phone"])):
        return jsonify({"error": "Enter a valid phone number."}), 400
    payment = data.get("payment_method", "Cash on Delivery")
    if payment not in ["Cash on Delivery", "UPI (demo)", "Card (demo)"]:
        payment = "Cash on Delivery"
    validated = []
    total = 0
    for item in data["items"]:
        try:
            pid, qty = int(item.get("id")), int(item.get("quantity"))
        except (TypeError, ValueError, AttributeError):
            return jsonify({"error": "Invalid cart item."}), 400
        product = db.session.get(Product, pid)
        if not product or qty < 1 or qty > 20:
            return jsonify({"error": "A cart item is unavailable or has an invalid quantity."}), 400
        if product.stock < qty:
            return jsonify({"error": f"Only {product.stock} left for {product.name}."}), 400
        validated.append((product, qty))
        total += product.price * qty
    if not validated:
        return jsonify({"error": "Your cart is empty."}), 400
    number = "SPX" + datetime.utcnow().strftime("%y%m%d") + str(os.urandom(3).hex()).upper()
    order = Order(order_number=number, customer_name=data["customer_name"].strip(),
                  email=data["email"].strip(), phone=str(data["phone"]).strip(),
                  address=data["address"].strip(), city=data["city"].strip(),
                  pincode=str(data["pincode"]).strip(), payment_method=payment, total=total)
    db.session.add(order)
    db.session.flush()
    for product, qty in validated:
        db.session.add(OrderItem(order_id=order.id, product_id=product.id,
                                 product_name=product.name, unit_price=product.price, quantity=qty))
        product.stock -= qty
    db.session.commit()
    return jsonify({"message": "Order placed successfully.", "order_number": number,
                    "total": total, "status": order.status}), 201

@app.get("/order-success")
def order_success():
    return render_template("success.html")



# ------------------------------ Admin dashboard ------------------------------
# Local demo defaults only. Configure SPORTIX_ADMIN_USERNAME, SPORTIX_ADMIN_PASSWORD, and SPORTIX_SECRET_KEY before deployment.
def admin_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("sportix_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("sportix_admin"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        expected_username = os.environ.get("SPORTIX_ADMIN_USERNAME", "admin")
        expected_password = os.environ.get("SPORTIX_ADMIN_PASSWORD", "admin")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == expected_username and password == expected_password:
            session.clear()
            session["sportix_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect username or password. Please try again.", "error")
    return render_template("admin_login.html")

@app.post("/admin/logout")
def admin_logout():
    session.pop("sportix_admin", None)
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    products = Product.query.order_by(Product.id.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).limit(100).all()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).scalar()
    return render_template("admin_dashboard.html", products=products, orders=orders,
        product_count=Product.query.count(), order_count=Order.query.count(),
        total_revenue=total_revenue, categories=CATEGORIES)

@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        product, error = product_from_form()
        if error:
            flash(error, "error")
            return render_template("admin_product_form.html", product=None, categories=CATEGORIES)
        db.session.add(product); db.session.commit()
        flash("Product added successfully.", "success")
        return redirect(url_for("admin_dashboard") + "#products")
    return render_template("admin_product_form.html", product=None, categories=CATEGORIES)

@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = db.session.get(Product, product_id)
    if not product: abort(404)
    if request.method == "POST":
        updated, error = product_from_form(product)
        if error:
            flash(error, "error")
            return render_template("admin_product_form.html", product=product, categories=CATEGORIES)
        db.session.commit()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_dashboard") + "#products")
    return render_template("admin_product_form.html", product=product, categories=CATEGORIES)

@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    product = db.session.get(Product, product_id)
    if product:
        db.session.delete(product); db.session.commit()
        flash("Product deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#products")

@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order: abort(404)
    status = request.form.get("status", "")
    if status in {"Placed", "Processing", "Shipped", "Delivered", "Cancelled"}:
        order.status = status; db.session.commit()
        flash(f"Order {order.order_number} updated to {status}.", "success")
    else:
        flash("Invalid order status.", "error")
    return redirect(url_for("admin_dashboard") + "#orders")

def product_from_form(product=None):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    brand = request.form.get("brand", "SPORTIX").strip() or "SPORTIX"
    image = request.form.get("image", "").strip()
    description = request.form.get("description", "").strip()
    try:
        price = int(request.form.get("price", "")); stock = int(request.form.get("stock", ""))
        rating = float(request.form.get("rating", "4.5")); reviews = int(request.form.get("reviews", "0"))
    except ValueError:
        return product, "Price, stock, rating and reviews must be valid numbers."
    if not name or not description or not image: return product, "Name, description and image URL are required."
    if category not in CATEGORIES: return product, "Please choose a valid category."
    if price < 0 or stock < 0 or reviews < 0 or not 0 <= rating <= 5:
        return product, "Price, stock and reviews must be non-negative; rating must be between 0 and 5."
    if product is None:
        product = Product(name=name, category=category, price=price, description=description,
            image=image, brand=brand, rating=rating, reviews=reviews, stock=stock)
    else:
        product.name, product.category, product.price = name, category, price
        product.description, product.image, product.brand = description, image, brand
        product.rating, product.reviews, product.stock = rating, reviews, stock
    return product, None

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)
