from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
import os
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

# ------------------------------
# Create the Flask app
# ------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-to-something-random")

# ------------------------------
# EMAIL SETTINGS - EDIT THESE!
# ------------------------------
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "eshetezerubabel@gmail.com")
MAIL_APP_PASSWORD = os.environ.get("MAIL_APP_PASSWORD", "jgirylzdimqhhqic")
MAIL_FROM_NAME = "Laundry Service"

# ------------------------------
# Make sure the database exists
# ------------------------------
init_db()


# ------------------------------
# CSRF Protection
# ------------------------------
@app.context_processor
def inject_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return {"csrf_token": session.get("csrf_token")}


def validate_csrf():
    token = request.form.get("csrf_token")
    if not token or token != session.get("csrf_token"):
        return False
    return True


# ------------------------------
# Rate Limiting for Login
# ------------------------------
login_attempts = {}


def is_rate_limited(username):
    now = datetime.now()
    if username in login_attempts:
        attempts, first_attempt = login_attempts[username]
        if now - first_attempt > timedelta(minutes=15):
            login_attempts[username] = (1, now)
            return False
        if attempts >= 5:
            return True
        login_attempts[username] = (attempts + 1, first_attempt)
        return False
    else:
        login_attempts[username] = (1, now)
        return False


# ------------------------------
# Login Required Decorator
# ------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------
# Email Sending Function
# ------------------------------
def send_email(to_email, subject, body):
    print("=" * 50)
    print(f"📧 ATTEMPTING TO SEND EMAIL")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    
    if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
        print("❌ Email not configured - skipping send.")
        return False

    if not to_email:
        print("❌ No email address provided.")
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_USERNAME}>"
        msg["To"] = to_email

        print("📧 Connecting to Gmail SMTP...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            print("📧 Logging in...")
            server.login(MAIL_USERNAME, MAIL_APP_PASSWORD)
            print("📧 Sending message...")
            server.send_message(msg)

        print(f"✅ EMAIL SENT SUCCESSFULLY to {to_email}!")
        print("=" * 50)
        return True
    except Exception as e:
        print(f"❌ FAILED TO SEND EMAIL: {e}")
        print("=" * 50)
        return False


# ------------------------------
# Notification Helper
# ------------------------------
def add_notification(message, conn=None):
    if conn:
        conn.execute("INSERT INTO notifications (message) VALUES (?)", (message,))
    else:
        with get_db() as db_conn:
            db_conn.execute("INSERT INTO notifications (message) VALUES (?)", (message,))


# ------------------------------
# Notification Context Processor
# ------------------------------
@app.context_processor
def inject_notifications():
    if "username" not in session:
        return {}
    with get_db() as conn:
        unread_count = conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()[0]
        recent_notifications = conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 5").fetchall()
    return {
        "unread_count": unread_count,
        "recent_notifications": recent_notifications,
    }


# ------------------------------
# Service Worker Route
# ------------------------------
@app.route("/sw.js")
def service_worker():
    response = app.send_static_file("sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


# ------------------------------
# Offline Page
# ------------------------------
@app.route("/offline.html")
def offline():
    return render_template("offline.html")


# ------------------------------
# Login Route
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if is_rate_limited(username):
            flash("Too many login attempts. Please try again in 15 minutes.")
            return redirect(url_for("login"))

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["username"] = user["username"]
            login_attempts.pop(username, None)
            return redirect(url_for("dashboard_advanced"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("login"))

    return render_template("login.html")


# ------------------------------
# Register Route
# ------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("register"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash("Username must be at least 3 characters.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        with get_db() as conn:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                flash("That username is already taken.")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))

        flash("✅ Account created! You can now log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


# ------------------------------
# ADVANCED ORDERS ROUTE (Simplified - 2 Statuses)
# ------------------------------
@app.route("/orders/advanced", methods=["GET", "POST"])
@login_required
def orders_advanced():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("orders_advanced"))

        customer_name = request.form.get("customer_name", "").strip()
        item_description = request.form.get("item_description", "").strip()
        price = request.form.get("price", "").strip()
        service_type = request.form.get("service_type", "Wash & Fold")
        payment_method = request.form.get("payment_method", "Cash")
        pickup_address = request.form.get("pickup_address", "").strip()
        delivery_address = request.form.get("delivery_address", "").strip()

        if not customer_name or not item_description or not price:
            flash("Please fill in required fields.")
            return redirect(url_for("orders_advanced"))

        try:
            price_value = float(price)
        except ValueError:
            flash("Price must be a number.")
            return redirect(url_for("orders_advanced"))

        with get_db() as conn:
            conn.execute("""
                INSERT INTO orders (
                    customer_name, item_description, price, 
                    service_type, payment_method, pickup_address, delivery_address, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer_name, item_description, price_value, 
                  service_type, payment_method, pickup_address, delivery_address, "Pending"))

        add_notification(f"📋 New order created for {customer_name}")
        flash("Order added successfully!")
        return redirect(url_for("orders_advanced"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    service_filter = request.args.get("service_type", "").strip()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if search:
        query += " AND customer_name LIKE ?"
        params.append(f"%{search}%")

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if service_filter:
        query += " AND service_type = ?"
        params.append(service_filter)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        orders = conn.execute(query, params).fetchall()

    return render_template("orders_advanced.html", 
                         orders=orders, 
                         search=search, 
                         status_filter=status_filter,
                         service_filter=service_filter)


# ------------------------------
# COMPLETE ORDER - Only 2 Statuses (Pending → Completed)
# ------------------------------
@app.route("/orders/<int:order_id>/complete", methods=["GET", "POST"])
@login_required
def complete_order(order_id):
    print("=" * 50)
    print(f"🔄 COMPLETING ORDER #{order_id}")
    
    if request.method == "POST" and not validate_csrf():
        flash("Invalid request. Please try again.")
        return redirect(url_for("orders_advanced"))
    
    email_sent = False
    
    with get_db() as conn:
        # Update order status to Completed
        conn.execute("UPDATE orders SET status = 'Completed' WHERE id = ?", (order_id,))
        print(f"✅ Order #{order_id} status updated to Completed")
        
        # Get order details
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        
        if order:
            print(f"📋 Order found: {order['customer_name']} - {order['item_description']}")
            
            # Find customer
            customer = conn.execute(
                "SELECT * FROM customers WHERE name = ? COLLATE NOCASE", 
                (order["customer_name"],)
            ).fetchone()
            
            if customer:
                print(f"👤 Customer found: {customer['name']} - Email: {customer['email']}")
                
                # SEND EMAIL IF CUSTOMER HAS EMAIL
                if customer["email"]:
                    email_sent = send_email(
                        to_email=customer["email"],
                        subject="🧺 Your Laundry Order is Complete!",
                        body=(
    f"🧺 Hi {customer['name']},\n\n"
    f"Your laundry is ready for pickup! 🎉\n\n"
    f"📋 Order #{order['id']}\n"
    f"👕 Items: {order['item_description']}\n"
    f"💰 Total: ${order['price']}\n\n"
    f"📍 Pickup at: 123 Main Street\n"
    f"⏰ Hours: 9:00 AM - 6:00 PM\n\n"
    f"Thank you for choosing us!\n"
    f"- Laundry Service Team"
)
                    )
                    
                    if email_sent:
                        add_notification(f"📧 Email sent to {customer['name']} for order #{order_id}", conn)
                        print("✅ Email notification added")
                    else:
                        add_notification(f"⚠️ Email failed for {customer['name']} order #{order_id}", conn)
                        print("❌ Email failed")
                else:
                    add_notification(f"✅ Order #{order_id} completed for {order['customer_name']} (no email)", conn)
                    print("ℹ️ No email address on file")
            else:
                print("⚠️ Customer not found in customers table")
                add_notification(f"✅ Order #{order_id} completed for {order['customer_name']}", conn)
        else:
            print("❌ Order not found!")
            flash("Order not found!")
            return redirect(url_for("orders_advanced"))

    print(f"✅ Order #{order_id} completed successfully!")
    print("=" * 50)
    
    if email_sent:
        flash(f"✅ Order #{order_id} completed! Email sent to customer! 📧")
    else:
        flash(f"✅ Order #{order_id} completed!")
    
    return redirect(url_for("orders_advanced"))


# ------------------------------
# ORDERS ROUTE (Original - Keep for compatibility)
# ------------------------------
@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("orders"))

        customer_name = request.form.get("customer_name", "").strip()
        item_description = request.form.get("item_description", "").strip()
        price = request.form.get("price", "").strip()

        if not customer_name or not item_description or not price:
            flash("Please fill in all fields.")
        else:
            try:
                price_value = float(price)
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO orders (customer_name, item_description, price) VALUES (?, ?, ?)",
                        (customer_name, item_description, price_value)
                    )
                flash("Order added!")
            except ValueError:
                flash("Price must be a number.")

        return redirect(url_for("orders"))

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if search:
        query += " AND customer_name LIKE ?"
        params.append(f"%{search}%")

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        all_orders = conn.execute(query, params).fetchall()

    return render_template("orders.html", orders=all_orders, search=search, status_filter=status_filter)


# ------------------------------
# Edit Order Route
# ------------------------------
@app.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def edit_order(order_id):
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("edit_order", order_id=order_id))

        customer_name = request.form.get("customer_name", "").strip()
        item_description = request.form.get("item_description", "").strip()
        price = request.form.get("price", "").strip()
        status = request.form.get("status", "").strip()

        if not customer_name or not item_description or not price:
            flash("Please fill in all fields.")
            return redirect(url_for("edit_order", order_id=order_id))

        try:
            price_value = float(price)
        except ValueError:
            flash("Price must be a number.")
            return redirect(url_for("edit_order", order_id=order_id))

        with get_db() as conn:
            conn.execute(
                """UPDATE orders
                   SET customer_name = ?, item_description = ?, price = ?, status = ?
                   WHERE id = ?""",
                (customer_name, item_description, price_value, status, order_id)
            )

        flash("Order updated!")
        return redirect(url_for("orders"))

    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    if order is None:
        flash("Order not found.")
        return redirect(url_for("orders"))

    return render_template("edit_order.html", order=order)


# ------------------------------
# Delete Order Route
# ------------------------------
@app.route("/orders/<int:order_id>/delete")
@login_required
def delete_order(order_id):
    with get_db() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    flash("Order deleted.")
    return redirect(url_for("orders"))


# ------------------------------
# NOTIFY CUSTOMER - Manual Email
# ------------------------------
@app.route("/orders/<int:order_id>/notify")
@login_required
def notify_customer(order_id):
    print(f"🔔 Manual notification for order #{order_id}")
    
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        customer = conn.execute(
            "SELECT * FROM customers WHERE name = ? COLLATE NOCASE", 
            (order["customer_name"],)
        ).fetchone()

    if customer and customer["email"]:
        email_sent = send_email(
            to_email=customer["email"],
            subject=f"Update on your laundry order #{order_id}",
            body=(
                f"🧺 Hi {customer['name']},\n\n"
                f"Your order #{order_id} is now: {order['status']}\n"
                f"Items: {order['item_description']}\n"
                f"Total: ${order['price']}\n\n"
                f"Thank you for choosing us!"
            )
        )
        if email_sent:
            flash(f"📧 Email sent to {customer['name']}")
        else:
            flash(f"❌ Failed to send email to {customer['name']}")
    else:
        flash("⚠️ Customer has no email address on file.")

    return redirect(url_for("orders_advanced"))


# ------------------------------
# REPORTS ROUTE
# ------------------------------
@app.route("/reports")
@login_required
def reports():
    with get_db() as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        total_revenue = conn.execute("SELECT COALESCE(SUM(price), 0) FROM orders").fetchone()[0]
        pending_count = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0]
        completed_count = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'").fetchone()[0]

        daily_rows = conn.execute("""
            SELECT DATE(created_at) AS day, COALESCE(SUM(price), 0) AS revenue
            FROM orders
            WHERE DATE(created_at) >= DATE('now', '-6 days')
            GROUP BY DATE(created_at)
        """).fetchall()

        revenue_by_day = {row["day"]: row["revenue"] for row in daily_rows}

        import datetime
        chart_labels = []
        chart_values = []
        for i in range(6, -1, -1):
            day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            chart_labels.append(day)
            chart_values.append(revenue_by_day.get(day, 0))

        top_customers = conn.execute("""
            SELECT customer_name, COUNT(*) AS order_count, SUM(price) AS total_spent
            FROM orders
            GROUP BY customer_name
            ORDER BY total_spent DESC
            LIMIT 5
        """).fetchall()

    return render_template(
        "reports.html",
        username=session["username"],
        total_orders=total_orders,
        total_revenue=total_revenue,
        pending_count=pending_count,
        completed_count=completed_count,
        chart_labels=chart_labels,
        chart_values=chart_values,
        top_customers=top_customers,
    )


# ------------------------------
# CUSTOMERS ROUTE
# ------------------------------
@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("customers"))

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Customer name is required.")
            return redirect(url_for("customers"))

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()

            if existing:
                flash(f"A customer named '{name}' is already registered.")
            else:
                conn.execute(
                    "INSERT INTO customers (name, phone, email, notes) VALUES (?, ?, ?, ?)",
                    (name, phone, email, notes)
                )
                add_notification(f"New customer registered: {name}", conn=conn)
                flash("Customer registered!")

        return redirect(url_for("customers"))

    with get_db() as conn:
        all_customers = conn.execute("SELECT * FROM customers ORDER BY name COLLATE NOCASE").fetchall()

    return render_template("customers.html", customers=all_customers)


# ------------------------------
# Customer Profile Route
# ------------------------------
@app.route("/customers/<int:customer_id>")
@login_required
def customer_profile(customer_id):
    with get_db() as conn:
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

        if customer is None:
            flash("Customer not found.")
            return redirect(url_for("customers"))

        customer_orders = conn.execute(
            "SELECT * FROM orders WHERE customer_name = ? ORDER BY id DESC",
            (customer["name"],)
        ).fetchall()

    total_spent = sum(order["price"] for order in customer_orders)
    pending_count = sum(1 for order in customer_orders if order["status"] == "Pending")
    completed_count = sum(1 for order in customer_orders if order["status"] == "Completed")

    return render_template(
        "customer_profile.html",
        customer=customer,
        orders=customer_orders,
        total_spent=total_spent,
        pending_count=pending_count,
        completed_count=completed_count,
    )


# ------------------------------
# Edit Customer Route
# ------------------------------
@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("edit_customer", customer_id=customer_id))

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Customer name is required.")
            return redirect(url_for("edit_customer", customer_id=customer_id))

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM customers WHERE name = ? COLLATE NOCASE AND id != ?",
                (name, customer_id)
            ).fetchone()

            if existing:
                flash(f"A customer named '{name}' already exists.")
                return redirect(url_for("edit_customer", customer_id=customer_id))

            conn.execute(
                "UPDATE customers SET name = ?, phone = ?, email = ?, notes = ? WHERE id = ?",
                (name, phone, email, notes, customer_id)
            )

        flash("Customer updated!")
        return redirect(url_for("customer_profile", customer_id=customer_id))

    with get_db() as conn:
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    if customer is None:
        flash("Customer not found.")
        return redirect(url_for("customers"))

    return render_template("edit_customer.html", customer=customer)


# ------------------------------
# Delete Customer Route
# ------------------------------
@app.route("/customers/<int:customer_id>/delete")
@login_required
def delete_customer(customer_id):
    with get_db() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    flash("Customer deleted.")
    return redirect(url_for("customers"))


# ------------------------------
# NOTIFICATIONS ROUTES
# ------------------------------
@app.route("/notifications")
@login_required
def notifications():
    with get_db() as conn:
        all_notifications = conn.execute("SELECT * FROM notifications ORDER BY id DESC").fetchall()
    return render_template("notifications.html", notifications=all_notifications)


@app.route("/notifications/mark_all_read")
@login_required
def mark_all_read():
    with get_db() as conn:
        conn.execute("UPDATE notifications SET is_read = 1")
    return redirect(url_for("notifications"))


# ------------------------------
# ADVANCED DASHBOARD ROUTE (Simplified - 2 Statuses)
# ------------------------------
@app.route("/dashboard/advanced")
@login_required
def dashboard_advanced():
    with get_db() as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0]
        completed_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'").fetchone()[0]
        
        revenue_today = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]
        
        orders_today = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]
        
        recent_orders = conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return render_template(
        "dashboard_advanced.html",
        username=session["username"],
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        revenue_today=revenue_today,
        orders_today=orders_today,
        recent_orders=recent_orders
    )


# ------------------------------
# DASHBOARD ROUTE (Original)
# ------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0]
        completed_today = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'Completed' AND DATE(created_at) = DATE('now')"
        ).fetchone()[0]
        revenue_today = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]

    return render_template(
        "dashboard.html",
        username=session["username"],
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_today=completed_today,
        revenue_today=revenue_today,
    )


# ------------------------------
# PROFILE ROUTE
# ------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid request. Please try again.")
            return redirect(url_for("profile"))

        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (session["username"],)).fetchone()

            if not user or not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.")
                return redirect(url_for("profile"))

            if not new_password or new_password != confirm_password:
                flash("New passwords do not match.")
                return redirect(url_for("profile"))

            new_hash = generate_password_hash(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (new_hash, session["username"])
            )

        flash("Password updated successfully!")
        return redirect(url_for("profile"))

    return render_template("profile.html", username=session["username"])


# ------------------------------
# LOGOUT ROUTE
# ------------------------------
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.")
    return redirect(url_for("login"))


# ------------------------------
# ERROR HANDLERS
# ------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    flash("Something went wrong. Please try again.")
    return render_template("error.html"), 500


@app.errorhandler(403)
def forbidden(e):
    flash("You don't have permission to access this page.")
    return render_template("error.html"), 403


# ------------------------------
# Run the app
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)