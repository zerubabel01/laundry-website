from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, init_db
import os
import smtplib
from email.mime.text import MIMEText

# ------------------------------
# Create the Flask app
# ------------------------------
app = Flask(__name__)
# Uses an environment variable in production if set, otherwise a fallback for local testing
app.secret_key = os.environ.get("SECRET_KEY", "change-this-to-something-random")

# ------------------------------
# Email settings (for sending real notification emails)
# Set these as environment variables - never hardcode a real password here.
# See the setup guide for how to create a Gmail "App Password".
# ------------------------------
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")       # e.g. yourshop@gmail.com
MAIL_APP_PASSWORD = os.environ.get("MAIL_APP_PASSWORD")  # the 16-character app password
MAIL_FROM_NAME = "Laundry Service"

# ------------------------------
# Make sure the database + users table exist
# ------------------------------
init_db()


# ------------------------------
# A "decorator" that protects a route.
# Put @login_required above any route you want to require login for.
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
# Helper: send a real email (used for customer notifications)
# Returns True if it sent successfully, False otherwise.
# Never crashes the app if email isn't set up or the send fails.
# ------------------------------
def send_email(to_email, subject, body):
    if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
        print("Email not configured - skipping send. (Set MAIL_USERNAME and MAIL_APP_PASSWORD.)")
        return False

    if not to_email:
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_USERNAME}>"
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_APP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# ------------------------------
# Helper: create an in-app notification (shown via the bell icon)
# ------------------------------
def add_notification(message):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (message) VALUES (?)", (message,)
    )
    conn.commit()
    conn.close()


# ------------------------------
# Runs before every page renders. Makes notification data available
# to every template automatically, so the bell icon works everywhere
# without repeating this query in every single route.
# ------------------------------
@app.context_processor
def inject_notifications():
    if "username" not in session:
        return {}
    conn = get_connection()
    unread_count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE is_read = 0"
    ).fetchone()[0]
    recent_notifications = conn.execute(
        "SELECT * FROM notifications ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return {
        "unread_count": unread_count,
        "recent_notifications": recent_notifications,
    }


# ------------------------------
# Route: Serve the service worker from the site root (not /static/)
# so it can control every page, not just files inside /static/.
# ------------------------------
@app.route("/sw.js")
def service_worker():
    return app.send_static_file("sw.js")


# ------------------------------
# Route: Login page
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Get the values the user typed in the form
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Look up the user in the real database
        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["username"] = user["username"]  # remember who's logged in
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("login"))

    # If it's just a normal page visit (GET), show the login form
    return render_template("login.html")


# ------------------------------
# Route: Register page
# ------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        conn = get_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            flash("That username is already taken.")
            conn.close()
            return redirect(url_for("register"))

        # Hash the password before storing it - never store plain text passwords
        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        conn.close()

        flash("Account created! You can now log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


# ------------------------------
# Route: Orders page (view + add orders)
# ------------------------------
@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    conn = get_connection()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        item_description = request.form.get("item_description", "").strip()
        price = request.form.get("price", "").strip()

        if not customer_name or not item_description or not price:
            flash("Please fill in all fields.")
        else:
            try:
                price_value = float(price)
                conn.execute(
                    "INSERT INTO orders (customer_name, item_description, price) VALUES (?, ?, ?)",
                    (customer_name, item_description, price_value)
                )
                conn.commit()
                flash("Order added!")
            except ValueError:
                flash("Price must be a number.")

        conn.close()
        return redirect(url_for("orders"))

    # GET request: read filters from the URL, e.g. /orders?search=john&status=Pending
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    # Build the SQL query piece by piece, based on which filters are active
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if search:
        query += " AND customer_name LIKE ?"
        params.append(f"%{search}%")

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY id DESC"

    all_orders = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "orders.html",
        orders=all_orders,
        search=search,
        status_filter=status_filter,
    )


# ------------------------------
# Route: Mark an order as Completed
# ------------------------------
@app.route("/orders/<int:order_id>/complete")
@login_required
def complete_order(order_id):
    conn = get_connection()

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.execute("UPDATE orders SET status = 'Completed' WHERE id = ?", (order_id,))
    conn.commit()

    if order:
        # Look up a matching customer profile to notify, if one exists
        customer = conn.execute(
            "SELECT * FROM customers WHERE name = ?", (order["customer_name"],)
        ).fetchone()

        email_sent = False
        if customer and customer["email"]:
            email_sent = send_email(
                to_email=customer["email"],
                subject="Your laundry order is ready!",
                body=(
                    f"Hi {customer['name']},\n\n"
                    f"Your order (#{order['id']}: {order['item_description']}) is complete "
                    f"and ready for pickup.\n\nThank you for your business!"
                )
            )

        if email_sent:
            add_notification(f"Order #{order['id']} completed - email sent to {customer['name']}.")
        else:
            add_notification(f"Order #{order['id']} completed for {order['customer_name']}.")

    conn.close()
    flash("Order marked as completed.")
    return redirect(url_for("orders"))


# ------------------------------
# Route: Edit an order
# ------------------------------
@app.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def edit_order(order_id):
    conn = get_connection()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        item_description = request.form.get("item_description", "").strip()
        price = request.form.get("price", "").strip()
        status = request.form.get("status", "").strip()

        if not customer_name or not item_description or not price:
            flash("Please fill in all fields.")
            conn.close()
            return redirect(url_for("edit_order", order_id=order_id))

        try:
            price_value = float(price)
        except ValueError:
            flash("Price must be a number.")
            conn.close()
            return redirect(url_for("edit_order", order_id=order_id))

        conn.execute(
            """UPDATE orders
               SET customer_name = ?, item_description = ?, price = ?, status = ?
               WHERE id = ?""",
            (customer_name, item_description, price_value, status, order_id)
        )
        conn.commit()
        conn.close()
        flash("Order updated!")
        return redirect(url_for("orders"))

    # GET request: load the existing order so the form can be pre-filled
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    conn.close()

    if order is None:
        flash("Order not found.")
        return redirect(url_for("orders"))

    return render_template("edit_order.html", order=order)


# ------------------------------
# Route: Delete an order
# ------------------------------
@app.route("/orders/<int:order_id>/delete")
@login_required
def delete_order(order_id):
    conn = get_connection()
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    flash("Order deleted.")
    return redirect(url_for("orders"))


# ------------------------------
# Route: Reports page
# ------------------------------
@app.route("/reports")
@login_required
def reports():
    conn = get_connection()

    # Overall totals
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(price), 0) FROM orders"
    ).fetchone()[0]

    # Breakdown by status (for a simple pending vs completed comparison)
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Pending'"
    ).fetchone()[0]
    completed_count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Completed'"
    ).fetchone()[0]

    # Revenue for each of the last 7 days, so we can draw a trend chart.
    # SQLite's DATE('now', '-N days') gives us a rolling window.
    daily_rows = conn.execute("""
        SELECT DATE(created_at) AS day, COALESCE(SUM(price), 0) AS revenue
        FROM orders
        WHERE DATE(created_at) >= DATE('now', '-6 days')
        GROUP BY DATE(created_at)
    """).fetchall()

    # Turn that into a dict for easy lookup, e.g. {"2026-07-01": 42.50}
    revenue_by_day = {row["day"]: row["revenue"] for row in daily_rows}

    # Build the last 7 days in order, filling in $0 for days with no orders
    import datetime
    chart_labels = []
    chart_values = []
    for i in range(6, -1, -1):
        day = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        chart_labels.append(day)
        chart_values.append(revenue_by_day.get(day, 0))

    # Top 5 customers by total amount spent
    top_customers = conn.execute("""
        SELECT customer_name, COUNT(*) AS order_count, SUM(price) AS total_spent
        FROM orders
        GROUP BY customer_name
        ORDER BY total_spent DESC
        LIMIT 5
    """).fetchall()

    conn.close()

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
# Route: Customers list + register a new customer
# ------------------------------
@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    conn = get_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Customer name is required.")
        else:
            # Check if a customer with this exact name already exists
            # (case-insensitive, so "john doe" and "John Doe" count as the same)
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
                conn.commit()
                add_notification(f"New customer registered: {name}")
                flash("Customer registered!")

        conn.close()
        return redirect(url_for("customers"))

    all_customers = conn.execute(
        "SELECT * FROM customers ORDER BY name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return render_template("customers.html", customers=all_customers)


# ------------------------------
# Route: Single customer profile - contact info + their order history
# ------------------------------
@app.route("/customers/<int:customer_id>")
@login_required
def customer_profile(customer_id):
    conn = get_connection()

    customer = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()

    if customer is None:
        conn.close()
        flash("Customer not found.")
        return redirect(url_for("customers"))

    # Match orders by name, since orders were built around a plain text field.
    # (Not a perfect match if two customers share a name, but fine for this scale.)
    customer_orders = conn.execute(
        "SELECT * FROM orders WHERE customer_name = ? ORDER BY id DESC",
        (customer["name"],)
    ).fetchall()

    total_spent = sum(order["price"] for order in customer_orders)
    pending_count = sum(1 for order in customer_orders if order["status"] == "Pending")
    completed_count = sum(1 for order in customer_orders if order["status"] == "Completed")

    conn.close()

    return render_template(
        "customer_profile.html",
        customer=customer,
        orders=customer_orders,
        total_spent=total_spent,
        pending_count=pending_count,
        completed_count=completed_count,
    )


# ------------------------------
# Route: Edit a customer's info
# ------------------------------
@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    conn = get_connection()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Customer name is required.")
            conn.close()
            return redirect(url_for("edit_customer", customer_id=customer_id))

        # Check no OTHER customer already has this name
        existing = conn.execute(
            "SELECT id FROM customers WHERE name = ? COLLATE NOCASE AND id != ?",
            (name, customer_id)
        ).fetchone()

        if existing:
            flash(f"A customer named '{name}' already exists.")
            conn.close()
            return redirect(url_for("edit_customer", customer_id=customer_id))

        conn.execute(
            "UPDATE customers SET name = ?, phone = ?, email = ?, notes = ? WHERE id = ?",
            (name, phone, email, notes, customer_id)
        )
        conn.commit()
        conn.close()
        flash("Customer updated!")
        return redirect(url_for("customer_profile", customer_id=customer_id))

    customer = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()
    conn.close()

    if customer is None:
        flash("Customer not found.")
        return redirect(url_for("customers"))

    return render_template("edit_customer.html", customer=customer)


# ------------------------------
# Route: Delete a customer
# ------------------------------
@app.route("/customers/<int:customer_id>/delete")
@login_required
def delete_customer(customer_id):
    conn = get_connection()
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()
    flash("Customer deleted.")
    return redirect(url_for("customers"))


# ------------------------------
# Route: View all notifications + mark them read
# ------------------------------
@app.route("/notifications")
@login_required
def notifications():
    conn = get_connection()
    all_notifications = conn.execute(
        "SELECT * FROM notifications ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("notifications.html", notifications=all_notifications)


@app.route("/notifications/mark_all_read")
@login_required
def mark_all_read():
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return redirect(url_for("notifications"))


# ------------------------------
# Route: Dashboard (shown after successful login)
# ------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()

    total_orders = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Pending'"
    ).fetchone()[0]

    completed_today = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Completed' AND DATE(created_at) = DATE('now')"
    ).fetchone()[0]

    revenue_today = conn.execute(
        "SELECT COALESCE(SUM(price), 0) FROM orders WHERE DATE(created_at) = DATE('now')"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        username=session["username"],
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_today=completed_today,
        revenue_today=revenue_today,
    )


# ------------------------------
# Route: Profile page (view username, change password)
# ------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (session["username"],)
        ).fetchone()

        # Step 1: verify they actually know their current password
        if not user or not check_password_hash(user["password_hash"], current_password):
            flash("Current password is incorrect.")
            conn.close()
            return redirect(url_for("profile"))

        # Step 2: make sure the new password fields match
        if not new_password or new_password != confirm_password:
            flash("New passwords do not match.")
            conn.close()
            return redirect(url_for("profile"))

        # Step 3: save the new hashed password
        new_hash = generate_password_hash(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (new_hash, session["username"])
        )
        conn.commit()
        conn.close()

        flash("Password updated successfully!")
        return redirect(url_for("profile"))

    return render_template("profile.html", username=session["username"])


# ------------------------------
# Route: Logout
# ------------------------------
@app.route("/logout")
def logout():
    session.pop("username", None)  # forget the logged-in user
    flash("You have been logged out.")
    return redirect(url_for("login"))


# ------------------------------
# Run the app
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True)