from werkzeug.security import generate_password_hash
from database import get_db

def create_user():
    username = input("Enter username: ")
    password = input("Enter password: ")
    
    password_hash = generate_password_hash(password)
    
    with get_db() as conn:
        # Check if user exists
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        if existing:
            print(f"❌ User '{username}' already exists!")
            return
        
        # Create the user
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        print(f"✅ User '{username}' created successfully!")

if __name__ == "__main__":
    create_user()