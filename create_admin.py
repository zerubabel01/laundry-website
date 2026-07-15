from werkzeug.security import generate_password_hash
from database import get_db

def create_admin():
    username = "admin"
    password = "admin123"
    
    password_hash = generate_password_hash(password)
    
    with get_db() as conn:
        # Check if user exists
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        if existing:
            print(f"⚠️ User 'admin' already exists! Delete the database to recreate.")
            return
        
        # Create the user
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        print(f"✅ Admin user created!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"   ⚠️  Change this password after first login!")

if __name__ == "__main__":
    create_admin()