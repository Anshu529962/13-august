# init_databases.py
import sqlite3
import os
from werkzeug.security import generate_password_hash
import datetime

def initialize_databases_on_startup():
    """Recreate essential databases if they don't exist"""
    PERSISTENT_DISK_PATH = os.environ.get('RENDER_PERSISTENT_DISK_PATH', '/opt/render/project/data')
    os.makedirs(PERSISTENT_DISK_PATH, exist_ok=True)
    
    admin_db_path = os.path.join(PERSISTENT_DISK_PATH, 'admin_users.db')
    
    # Only create if database doesn't exist
    if not os.path.exists(admin_db_path):
        conn = sqlite3.connect(admin_db_path)
        
        # Create user schema
        conn.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                user_type TEXT DEFAULT 'student',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create default admin user
        admin_password = generate_password_hash('admin123')
        conn.execute('''
            INSERT INTO users (username, email, password, user_type) 
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@mbbsqbank.com', admin_password, 'admin'))
        
        # Create your student account
        student_password = generate_password_hash('student123')
        conn.execute('''
            INSERT INTO users (username, email, password, user_type) 
            VALUES (?, ?, ?, ?)
        ''', ('priyanshuguha', 'priyanshu62@gmail.com', student_password, 'student'))
        
        conn.commit()
        conn.close()
        
        print("✅ Database initialized with default accounts")

# Call this at app startup
if __name__ == "__main__":
    initialize_databases_on_startup()
