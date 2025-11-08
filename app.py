from __future__ import annotations

import os
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------
# App & DB setup
# ------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///macrotracker.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ------------------------------
# Models
# ------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="user", lazy=True)
    meals = db.relationship("Meal", backref="user", lazy=True)
    consumptions = db.relationship("Consumption", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    calories_per_100g = db.Column(db.Float, nullable=False, default=0.0)
    protein_g_per_100g = db.Column(db.Float, nullable=False, default=0.0)
    carbs_g_per_100g = db.Column(db.Float, nullable=False, default=0.0)
    fat_g_per_100g = db.Column(db.Float, nullable=False, default=0.0)


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    name = db.Column(db.String(80), nullable=False)


class Consumption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    meal_id = db.Column(db.Integer, db.ForeignKey("meal.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity_g = db.Column(db.Float, nullable=False, default=0.0)  # grams
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    meal = db.relationship("Meal", lazy="joined")
    product = db.relationship("Product", lazy="joined")


# ------------------------------
# Auth utilities
# ------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ------------------------------
# DB init & default admin
# ------------------------------
with app.app_context():
    db.create_all()
    # Ensure at least one admin exists
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        admin = User(username=admin_username, email=admin_email, is_admin=True, is_approved=True)
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"[INFO] Created default admin: {admin_email} / {admin_password} (change ASAP)")


# ------------------------------
# Helpers
# ------------------------------
def totals_for_date(user_id: int, target_date: date):
    """Compute total calories/macros for a given date for the user."""
    consumptions = (Consumption.query
                    .filter_by(user_id=user_id)
                    .join(Meal)
                    .filter(Meal.date == target_date)
                    .all())
    totals = {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }
    for c in consumptions:
        factor = c.quantity_g / 100.0
        totals["calories"] += c.product.calories_per_100g * factor
        totals["protein"]  += c.product.protein_g_per_100g * factor
        totals["carbs"]    += c.product.carbs_g_per_100g * factor
        totals["fat"]      += c.product.fat_g_per_100g * factor
    return totals


# ------------------------------
# Routes: Auth
# ------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("signup.html")

        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("Username or email already exists.", "danger")
            return render_template("signup.html")

        user = User(username=username, email=email, is_admin=False, is_approved=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Signup successful! Wait for admin approval before logging in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return render_template("login.html")
        if not user.is_approved:
            flash("Your account is pending approval.", "warning")
            return render_template("login.html")
        login_user(user)
        flash("Logged in.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# ------------------------------
# Routes: Admin
# ------------------------------
@app.route("/admin/pending")
@admin_required
def admin_pending():
    users = User.query.filter_by(is_approved=False).all()
    return render_template("admin_pending.html", users=users)


@app.route("/admin/approve/<int:user_id>", methods=["POST"])
@admin_required
def admin_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"Approved {user.email}.", "success")
    return redirect(url_for("admin_pending"))


@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)


# ------------------------------
# Routes: Core pages
# ------------------------------
@app.route("/")
@login_required
def dashboard():
    today = date.today()
    totals = totals_for_date(current_user.id, today)
    meals = Meal.query.filter_by(user_id=current_user.id, date=today).order_by(Meal.name).all()
    consumptions = (Consumption.query.filter_by(user_id=current_user.id)
                    .join(Meal).filter(Meal.date == today).all())
    return render_template("dashboard.html", totals=totals, meals=meals, consumptions=consumptions, today=today)


@app.route("/history")
@login_required
def history():
    # group by date for the last 14 days
    from sqlalchemy import func
    rows = (db.session.query(Meal.date)
            .filter_by(user_id=current_user.id)
            .group_by(Meal.date)
            .order_by(Meal.date.desc())
            .limit(14)
            .all())
    dates = [r[0] for r in rows]
    per_day = []
    for d in dates:
        per_day.append({"date": d, "totals": totals_for_date(current_user.id, d)})
    return render_template("history.html", per_day=per_day)


# ------------------------------
# Routes: Products
# ------------------------------
@app.route("/products")
@login_required
def products():
    items = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    return render_template("products.html", items=items)


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cal = float(request.form.get("calories", 0) or 0)
        p = float(request.form.get("protein", 0) or 0)
        c = float(request.form.get("carbs", 0) or 0)
        f = float(request.form.get("fat", 0) or 0)
        if not name:
            flash("Name is required.", "danger")
            return render_template("product_form.html")
        prod = Product(user_id=current_user.id, name=name,
                       calories_per_100g=cal, protein_g_per_100g=p,
                       carbs_g_per_100g=c, fat_g_per_100g=f)
        db.session.add(prod)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html")


@app.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def product_delete(pid):
    prod = Product.query.filter_by(id=pid, user_id=current_user.id).first_or_404()
    db.session.delete(prod)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("products"))


# ------------------------------
# Routes: Meals
# ------------------------------
@app.route("/meals")
@login_required
def meals():
    items = Meal.query.filter_by(user_id=current_user.id).order_by(Meal.date.desc(), Meal.name).all()
    return render_template("meals.html", items=items)


@app.route("/meals/new", methods=["GET", "POST"])
@login_required
def meal_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip() or "Meal"
        date_str = request.form.get("date") or ""
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            d = date.today()
        meal = Meal(user_id=current_user.id, name=name, date=d)
        db.session.add(meal)
        db.session.commit()
        flash("Meal created.", "success")
        return redirect(url_for("meals"))
    return render_template("meal_form.html")


@app.route("/consumptions/new", methods=["GET", "POST"])
@login_required
def consumption_new():
    meals = Meal.query.filter_by(user_id=current_user.id).order_by(Meal.date.desc()).all()
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    if request.method == "POST":
        meal_id = int(request.form.get("meal_id"))
        product_id = int(request.form.get("product_id"))
        qty = float(request.form.get("quantity_g", 0) or 0)
        meal = Meal.query.filter_by(id=meal_id, user_id=current_user.id).first_or_404()
        prod = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
        c = Consumption(user_id=current_user.id, meal_id=meal.id, product_id=prod.id, quantity_g=qty)
        db.session.add(c)
        db.session.commit()
        flash("Consumption added.", "success")
        return redirect(url_for("dashboard"))
    return render_template("consumption_form.html", meals=meals, products=products)


# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)
