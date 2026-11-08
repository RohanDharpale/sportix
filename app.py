from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime, timedelta
import hmac
import json
import os, re
import secrets
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///sportix.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
IS_PRODUCTION = (
    os.environ.get("SPORTIX_ENV", "").casefold() == "production"
    or os.environ.get("FLASK_ENV", "").casefold() == "production"
)
if IS_PRODUCTION:
    secret_key = os.environ.get("SPORTIX_SECRET_KEY", "")
    admin_username = os.environ.get("SPORTIX_ADMIN_USERNAME", "")
    admin_password = os.environ.get("SPORTIX_ADMIN_PASSWORD", "")
    if (len(secret_key) < 32 or secret_key == "change-this-secret-before-deployment"
            or not admin_username or len(admin_password) < 12):
        raise RuntimeError(
            "Production requires SPORTIX_SECRET_KEY (at least 32 characters), "
            "SPORTIX_ADMIN_USERNAME, and SPORTIX_ADMIN_PASSWORD (at least 12 characters)."
        )
app.config["SECRET_KEY"] = os.environ.get("SPORTIX_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
db = SQLAlchemy(app)

@app.context_processor
def inject_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["_csrf_token"]}

@app.before_request
def protect_admin_posts():
    if request.method == "POST" and request.path.startswith("/admin"):
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
            abort(400, description="The form expired or was invalid. Please reload and try again.")

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
    sizes = db.Column(db.String(200), nullable=False, default="")
    gallery = db.Column(db.Text, nullable=False, default="[]")
    size_stock = db.Column(db.Text, nullable=False, default="{}")

    def get_size_stock(self):
        return json.loads(self.size_stock or "{}")

    @property
    def size_stock_text(self):
        return ", ".join(f"{size}:{quantity}" for size, quantity in self.get_size_stock().items())

    def available_stock(self, size):
        size_stock = self.get_size_stock()
        return int(size_stock[size]) if size in size_stock else (
            0 if size_stock else self.stock
        )

    def as_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category,
                "price": self.price, "description": self.description, "image": self.image,
                "brand": self.brand, "rating": self.rating, "reviews": self.reviews,
                "stock": self.stock, "sizes": [size for size in self.sizes.split(",") if size],
                "images": [self.image, *json.loads(self.gallery or "[]")],
                "size_stock": self.get_size_stock()}

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

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
    size = db.Column(db.String(30), nullable=False, default="Standard")

class NewsletterSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

SEED = [
    ("SS Ton Cricket Bat", "Cricket Equipment", 6499, "A balanced English-willow style bat built for confident shots and practice sessions.", "https://images.unsplash.com/photo-1531415074968-036ba1b575da?auto=format&fit=crop&w=900&q=85", "SS", 4.8, 34),
    ("Adidas Football (Size 5)", "Football Equipment", 1999, "Durable training football with a dependable touch for matches and practice.", "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=900&q=85", "Adidas", 4.6, 18),
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
    ("Cricket Training Stumps", "Cricket Equipment", 1199, "Portable stumps set for net practice, coaching and backyard games.", "https://images.unsplash.com/photo-1624526267942-ab0ff8a3e972?auto=format&fit=crop&w=900&q=85", "SG", 4.3, 12),
    ("Everyday Sports Socks", "Running Shoes", 399, "Comfortable, supportive socks for daily runs and gym sessions.", "https://images.unsplash.com/photo-1556906781-9a412961c28c?auto=format&fit=crop&w=900&q=85", "SPORTIX", 4.1, 6),
]

IMAGE_URL_MIGRATIONS = {
    "https://images.unsplash.com/photo-1614632537423-1e6c2e7e0c4e?auto=format&fit=crop&w=900&q=85":
        "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1593766827228-8737b1cd1474?auto=format&fit=crop&w=900&q=85":
        "https://images.unsplash.com/photo-1624526267942-ab0ff8a3e972?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1586350977771-b3b0afd6d1e6?auto=format&fit=crop&w=900&q=85":
        "https://images.unsplash.com/photo-1556906781-9a412961c28c?auto=format&fit=crop&w=900&q=85",
}

def seed_products():
    if Product.query.count() == 0:
        for name, category, price, desc, image, brand, rating, reviews in SEED:
            db.session.add(Product(name=name, category=category, price=price, description=desc,
                                   image=image, brand=brand, rating=rating, reviews=reviews))
        db.session.commit()

with app.app_context():
    db.create_all()
    existing_columns = {
        table: {column["name"] for column in db.inspect(db.engine).get_columns(table)}
        for table in ("product", "order_item")
    }
    if "sizes" not in existing_columns["product"]:
        db.session.execute(db.text("ALTER TABLE product ADD COLUMN sizes VARCHAR(200) NOT NULL DEFAULT ''"))
    if "size" not in existing_columns["order_item"]:
        db.session.execute(db.text("ALTER TABLE order_item ADD COLUMN size VARCHAR(30) NOT NULL DEFAULT 'Standard'"))
    if "gallery" not in existing_columns["product"]:
        db.session.execute(db.text("ALTER TABLE product ADD COLUMN gallery TEXT NOT NULL DEFAULT '[]'"))
    if "size_stock" not in existing_columns["product"]:
        db.session.execute(db.text("ALTER TABLE product ADD COLUMN size_stock TEXT NOT NULL DEFAULT '{}'"))
    db.session.commit()
    for old_url, new_url in IMAGE_URL_MIGRATIONS.items():
        db.session.query(Product).filter_by(image=old_url).update(
            {"image": new_url}, synchronize_session=False
        )
        for product in Product.query.filter(Product.gallery.contains(old_url)).all():
            gallery = json.loads(product.gallery or "[]")
            updated_gallery = [IMAGE_URL_MIGRATIONS.get(image, image) for image in gallery]
            if updated_gallery != gallery:
                product.gallery = json.dumps(updated_gallery)
    db.session.commit()
    if Category.query.count() == 0:
        db.session.add_all(Category(name=name) for name in CATEGORIES)
        db.session.commit()
    seed_products()

def get_categories():
    return [category.name for category in Category.query.order_by(Category.name.asc()).all()]

@app.get("/")
def home():
    featured = Product.query.order_by(Product.rating.desc()).limit(8).all()
    best_sellers = db.session.query(OrderItem.product_id).join(
        Order, Order.id == OrderItem.order_id
    ).filter(Order.status != "Cancelled").group_by(
        OrderItem.product_id
    ).order_by(db.desc(db.func.sum(OrderItem.quantity))).limit(3).all()
    new_arrivals = Product.query.order_by(Product.id.desc()).limit(4).all()
    return render_template("index.html", categories=get_categories(), featured=featured,
                           best_seller_ids=[product_id for (product_id,) in best_sellers],
                           new_arrivals=new_arrivals)

@app.get("/shop")
def shop():
    return render_template("shop.html", categories=get_categories())

@app.get("/products/<int:product_id>")
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    related = Product.query.filter(
        Product.category == product.category, Product.id != product.id
    ).order_by(Product.rating.desc()).limit(4).all()
    return render_template("product.html", product=product, related=related,
                           images=product.as_dict()["images"])

@app.get("/wishlist")
def wishlist():
    return render_template("wishlist.html")

@app.post("/api/newsletter")
def subscribe_newsletter():
    data = request.get_json(silent=True)
    email = data.get("email", "").strip().lower() if isinstance(data, dict) and isinstance(data.get("email"), str) else ""
    if len(email) > 120 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Enter a valid email address."}), 400
    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        return jsonify({"message": "You’re already on the SPORTIX list."}), 200
    db.session.add(NewsletterSubscriber(email=email))
    db.session.commit()
    return jsonify({"message": "You’re in. Watch this space for fresh drops and training inspiration."}), 201

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
    if category in get_categories():
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
    elif sort == "recent":
        query = query.order_by(Product.id.desc())
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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Order details must be sent as a valid object."}), 400
    required = ["customer_name", "email", "phone", "address", "city", "pincode", "items"]
    text_fields = required[:-1]
    if any(not isinstance(data.get(field), str) or not data[field].strip() for field in text_fields):
        return jsonify({"error": "Please complete all required fields and add items to your cart."}), 400
    if not isinstance(data.get("items"), list) or not data["items"]:
        return jsonify({"error": "Please complete all required fields and add items to your cart."}), 400
    if (len(data["customer_name"].strip()) > 100 or len(data["email"].strip()) > 120
            or len(data["phone"].strip()) > 20 or len(data["address"].strip()) > 500
            or len(data["city"].strip()) > 80):
        return jsonify({"error": "One or more order details are too long."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not re.match(r"^[0-9]{6}$", str(data["pincode"])):
        return jsonify({"error": "Enter a valid 6-digit PIN code."}), 400
    if not re.match(r"^[0-9+\-\s]{10,15}$", str(data["phone"])):
        return jsonify({"error": "Enter a valid phone number."}), 400
    payment = data.get("payment_method", "Cash on Delivery")
    if payment not in ["Cash on Delivery", "UPI (demo)", "Card (demo)"]:
        return jsonify({"error": "Choose a valid payment method."}), 400
    validated = []
    total = 0
    requested_stock = {}
    requested_size_stock = {}
    for item in data["items"]:
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid cart item."}), 400
        try:
            raw_id, raw_quantity = item.get("id"), item.get("quantity")
            pid, qty = int(raw_id), int(raw_quantity)
        except (TypeError, ValueError, AttributeError):
            return jsonify({"error": "Invalid cart item."}), 400
        if str(pid) != str(raw_id).strip() or str(qty) != str(raw_quantity).strip():
            return jsonify({"error": "Cart product IDs and quantities must be whole numbers."}), 400
        product = db.session.get(Product, pid)
        if not product or qty < 1 or qty > 20:
            return jsonify({"error": "A cart item is unavailable or has an invalid quantity."}), 400
        size = str(item.get("size", "Standard")).strip()
        available_sizes = [value for value in product.sizes.split(",") if value]
        if (available_sizes and size not in available_sizes) or (not available_sizes and size != "Standard"):
            return jsonify({"error": f"Choose an available size for {product.name}."}), 400
        validated.append((product, qty, size))
        requested_stock[product.id] = requested_stock.get(product.id, 0) + qty
        key = (product.id, size)
        requested_size_stock[key] = requested_size_stock.get(key, 0) + qty
        total += product.price * qty
    if not validated:
        return jsonify({"error": "Your cart is empty."}), 400
    for product, _, _ in validated:
        if product.stock < requested_stock[product.id]:
            return jsonify({"error": f"Only {product.stock} left for {product.name}."}), 400
    for (product_id, size), quantity in requested_size_stock.items():
        product = db.session.get(Product, product_id)
        size_stock = product.get_size_stock()
        if size_stock and size_stock.get(size, 0) < quantity:
            return jsonify({
                "error": f"Only {size_stock.get(size, 0)} left in size {size} for {product.name}."
            }), 400
    number = "SPX" + datetime.utcnow().strftime("%y%m%d") + str(os.urandom(3).hex()).upper()
    order = Order(order_number=number, customer_name=data["customer_name"].strip(),
                  email=data["email"].strip(), phone=str(data["phone"]).strip(),
                  address=data["address"].strip(), city=data["city"].strip(),
                  pincode=str(data["pincode"]).strip(), payment_method=payment, total=total)
    db.session.add(order)
    db.session.flush()
    for product, qty, size in validated:
        db.session.add(OrderItem(order_id=order.id, product_id=product.id,
                                 product_name=product.name, unit_price=product.price, quantity=qty,
                                 size=size))
        product.stock -= qty
    for product_id in {product_id for product_id, _ in requested_size_stock}:
        product = db.session.get(Product, product_id)
        size_stock = product.get_size_stock()
        if size_stock:
            for (deduction_product_id, deduction_size), quantity in requested_size_stock.items():
                if deduction_product_id == product_id:
                    size_stock[deduction_size] -= quantity
            product.size_stock = json.dumps(size_stock)
    db.session.commit()
    return jsonify({"message": "Order placed successfully.", "order_number": number,
                    "total": total, "status": order.status}), 201

@app.get("/order-success")
def order_success():
    return render_template("success.html")



# ------------------------------ Admin dashboard ------------------------------
# Local demo defaults only. Production requires explicitly configured credentials and a secret key.
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
        if (hmac.compare_digest(username.encode("utf-8"), expected_username.encode("utf-8"))
                and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))):
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
    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Order.total), 0)
    ).filter(Order.status != "Cancelled").scalar()
    customer_count = db.session.query(db.func.count(db.distinct(Order.email))).scalar()
    today = datetime.utcnow().date()
    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    week_orders = Order.query.filter(
        Order.created_at >= week_start, Order.status != "Cancelled"
    ).all()
    revenue_by_day = {day: 0 for day in (today - timedelta(days=i) for i in range(6, -1, -1))}
    for order in week_orders:
        revenue_by_day[order.created_at.date()] += order.total
    revenue_trend = [
        {"label": day.strftime("%a"), "date": day.strftime("%d %b"), "revenue": revenue}
        for day, revenue in revenue_by_day.items()
    ]
    max_daily_revenue = max((day["revenue"] for day in revenue_trend), default=0)
    status_counts = {
        status: Order.query.filter_by(status=status).count()
        for status in ("Placed", "Processing", "Shipped", "Delivered", "Cancelled")
    }
    best_sellers = db.session.query(
        OrderItem.product_name, db.func.sum(OrderItem.quantity).label("units")
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.status != "Cancelled"
    ).group_by(OrderItem.product_name).order_by(db.desc("units")).limit(5).all()
    low_stock = Product.query.filter(Product.stock < 6).order_by(Product.stock.asc()).all()
    return render_template("admin_dashboard.html", products=products, orders=orders,
        product_count=Product.query.count(), order_count=Order.query.count(),
        total_revenue=total_revenue, categories=get_categories(),
        category_records=Category.query.order_by(Category.name.asc()).all(),
        customer_count=customer_count, revenue_trend=revenue_trend,
        max_daily_revenue=max_daily_revenue, status_counts=status_counts,
        best_sellers=best_sellers, low_stock=low_stock)

@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        product, error = product_from_form()
        if error:
            flash(error, "error")
            return render_template("admin_product_form.html", product=None, categories=get_categories())
        db.session.add(product); db.session.commit()
        flash("Product added successfully.", "success")
        return redirect(url_for("admin_dashboard") + "#products")
    return render_template("admin_product_form.html", product=None, categories=get_categories())

@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    product = db.session.get(Product, product_id)
    if not product: abort(404)
    if request.method == "POST":
        updated, error = product_from_form(product)
        if error:
            flash(error, "error")
            return render_template("admin_product_form.html", product=product, categories=get_categories())
        db.session.commit()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin_dashboard") + "#products")
    return render_template("admin_product_form.html", product=product, categories=get_categories())

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

@app.post("/admin/categories")
@admin_required
def admin_category_create():
    name = request.form.get("name", "").strip()
    if not name or len(name) > 80:
        flash("Category names must contain 1–80 characters.", "error")
    elif any(category.casefold() == name.casefold() for category in get_categories()):
        flash("That category already exists.", "error")
    else:
        db.session.add(Category(name=name))
        db.session.commit()
        flash(f"Category “{name}” added.", "success")
    return redirect(url_for("admin_dashboard") + "#categories-admin")

@app.post("/admin/categories/<int:category_id>/delete")
@admin_required
def admin_category_delete(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        abort(404)
    if category.name in CATEGORIES:
        flash("Core SPORTIX categories cannot be removed.", "error")
    elif Product.query.filter_by(category=category.name).first():
        flash("Move or remove products in this category before deleting it.", "error")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category removed.", "success")
    return redirect(url_for("admin_dashboard") + "#categories-admin")

def product_from_form(product=None):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    brand = request.form.get("brand", "SPORTIX").strip() or "SPORTIX"
    image = request.form.get("image", "").strip()
    uploads = []
    primary_upload = request.files.get("image_file")
    gallery_uploads = request.files.getlist("gallery_files")
    for upload in ([primary_upload] if primary_upload else []) + gallery_uploads:
        if not upload or not upload.filename:
            continue
        safe_name = secure_filename(upload.filename)
        if not safe_name:
            return product, "Choose a valid image file."
        extension = os.path.splitext(safe_name)[1].lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            return product, "Upload JPG, PNG or WebP product images."
        signature = upload.stream.read(12)
        upload.stream.seek(0)
        valid_signature = (
            (extension == ".png" and signature.startswith(b"\x89PNG\r\n\x1a\n"))
            or (extension in {".jpg", ".jpeg"} and signature.startswith(b"\xff\xd8\xff"))
            or (extension == ".webp" and signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
        )
        if not valid_signature:
            return product, "An uploaded file does not match its image format."
        uploads.append((upload, f"{os.urandom(8).hex()}-{safe_name}", upload is primary_upload))
    if len(uploads) > 6:
        return product, "Upload up to six product images at a time."
    sizes = ",".join(dict.fromkeys(
        size.strip() for size in request.form.get("sizes", "").split(",") if size.strip()
    ))
    description = request.form.get("description", "").strip()
    try:
        price = int(request.form.get("price", "")); stock = int(request.form.get("stock", ""))
        rating = float(request.form.get("rating", "4.5")); reviews = int(request.form.get("reviews", "0"))
    except ValueError:
        return product, "Price, stock, rating and reviews must be valid numbers."
    size_stock_text = request.form.get("size_stock", "").strip()
    size_stock = {}
    if size_stock_text:
        if len(size_stock_text) > 500:
            return product, "Size-level stock details must be 500 characters or fewer."
        if not sizes:
            return product, "Add available sizes before setting size-level stock."
        try:
            for entry in size_stock_text.split(","):
                size, quantity = entry.rsplit(":", 1)
                size, quantity = size.strip(), int(quantity.strip())
                if size in size_stock or size not in sizes.split(",") or quantity < 0:
                    raise ValueError
                size_stock[size] = quantity
        except ValueError:
            return product, "Use valid, unique size quantities such as S:4, M:8, L:3."
        if set(size_stock) != set(sizes.split(",")):
            return product, "Enter a stock quantity for every available size."
        if sum(size_stock.values()) != stock:
            return product, "The size quantities must add up to the total stock quantity."
    if not name or not description or (not image and not uploads):
        return product, "Name, description and an image URL or upload are required."
    if len(sizes) > 200 or any(len(size) > 30 for size in sizes.split(",") if size):
        return product, "Size options must be 30 characters or fewer and fit within 200 characters total."
    if image and not image.startswith(("http://", "https://", "/static/")):
        return product, "Use a secure HTTP(S) URL or a local image path."
    if category not in get_categories(): return product, "Please choose a valid category."
    if price < 0 or stock < 0 or reviews < 0 or not 0 <= rating <= 5:
        return product, "Price, stock and reviews must be non-negative; rating must be between 0 and 5."
    if uploads:
        upload_dir = os.path.join(app.root_path, "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        uploaded_urls = []
        main_upload_url = None
        for upload, filename, is_primary in uploads:
            upload.save(os.path.join(upload_dir, filename))
            uploaded_url = url_for("static", filename=f"uploads/{filename}")
            uploaded_urls.append(uploaded_url)
            if is_primary:
                main_upload_url = uploaded_url
        if main_upload_url:
            image = main_upload_url
        elif not image:
            image = uploaded_urls.pop(0)
        existing_gallery = json.loads(product.gallery or "[]") if product else []
        gallery = existing_gallery + [
            url for url in uploaded_urls if url != image and url not in existing_gallery
        ]
    else:
        gallery = json.loads(product.gallery or "[]") if product else []
    if product is None:
        product = Product(name=name, category=category, price=price, description=description,
            image=image, brand=brand, rating=rating, reviews=reviews, stock=stock,
            sizes=sizes, gallery=json.dumps(gallery), size_stock=json.dumps(size_stock))
    else:
        product.name, product.category, product.price = name, category, price
        product.description, product.image, product.brand, product.sizes = description, image, brand, sizes
        product.gallery = json.dumps(gallery)
        product.size_stock = json.dumps(size_stock)
        product.rating, product.reviews, product.stock = rating, reviews, stock
    return product, None

@app.get("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok", "database": "ok"})

if __name__ == "__main__":
    app.run(debug=not IS_PRODUCTION and os.environ.get("FLASK_DEBUG", "").casefold() in {"1", "true"})
