from database import get_db

def list_users():
    with get_db() as conn:
        users = conn.execute("SELECT id, username FROM users").fetchall()
        if users:
            print("✅ Users in database:")
            for user in users:
                print(f"  - ID: {user['id']}, Username: {user['username']}")
        else:
            print("❌ No users found in database!")

if __name__ == "__main__":
    list_users()