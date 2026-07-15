from database import get_db

def view_database():
    with get_db() as conn:
        print("=" * 50)
        print("USERS:")
        users = conn.execute("SELECT * FROM users").fetchall()
        for user in users:
            print(f"  ID: {user['id']}, Username: {user['username']}")
            print(f"  Password Hash: {user['password_hash'][:20]}...")
        
        print("\n" + "=" * 50)
        print("ORDERS:")
        orders = conn.execute("SELECT * FROM orders").fetchall()
        for order in orders[:5]:  # Show first 5
            print(f"  #{order['id']}: {order['customer_name']} - {order['item_description']}")
        
        print("\n" + "=" * 50)
        print("CUSTOMERS:")
        customers = conn.execute("SELECT * FROM customers").fetchall()
        for customer in customers[:5]:
            print(f"  {customer['name']} - {customer['email'] or 'No email'}")

if __name__ == "__main__":
    view_database()
    