import sqlite3
import os
from werkzeug.security import generate_password_hash
import datetime

def get_persistent_disk_path():
    """Get appropriate persistent disk path based on environment"""
    if os.path.exists('/opt/render'):
        # Production environment (Render)
        return os.environ.get('RENDER_PERSISTENT_DISK_PATH', '/opt/render/project/data')
    else:
        # Local development environment
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, 'data')

# Set persistent disk path
PERSISTENT_DISK_PATH = get_persistent_disk_path()

def migrate_ephemeral_users():
    """Check for users in ephemeral storage and migrate them to persistent storage"""
    ephemeral_paths = [
        '/opt/render/project/src/admin_users.db',
        '/opt/render/project/src/data/databases/admin_users.db'
    ]
    
    persistent_db_path = os.path.join(PERSISTENT_DISK_PATH, 'admin_users.db')
    
    for ephemeral_path in ephemeral_paths:
        if os.path.exists(ephemeral_path):
            print(f"🔄 Found ephemeral user database: {ephemeral_path}")
            
            try:
                # Connect to both databases
                ephemeral_conn = sqlite3.connect(ephemeral_path)
                persistent_conn = sqlite3.connect(persistent_db_path)
                
                # Get all users from ephemeral storage
                ephemeral_users = ephemeral_conn.execute('''
                    SELECT username, email, password, first_name, last_name, 
                           user_type, is_active, created_at 
                    FROM users
                ''').fetchall()
                
                migrated_count = 0
                
                for user in ephemeral_users:
                    username, email, password, first_name, last_name, user_type, is_active, created_at = user
                    
                    try:
                        # Check if user already exists in persistent storage
                        existing = persistent_conn.execute(
                            'SELECT COUNT(*) FROM users WHERE email = ?', (email,)
                        ).fetchone()[0]
                        
                        if existing == 0:
                            persistent_conn.execute('''
                                INSERT INTO users 
                                (username, email, password, first_name, last_name, 
                                 user_type, is_active, created_at) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (username, email, password, first_name, last_name, 
                                  user_type, is_active, created_at))
                            
                            migrated_count += 1
                            print(f"✅ Migrated user: {email}")
                        else:
                            print(f"⚠️ User already exists: {email}")
                            
                    except Exception as e:
                        print(f"❌ Error migrating {email}: {e}")
                
                persistent_conn.commit()
                ephemeral_conn.close()
                persistent_conn.close()
                
                print(f"📊 Migration completed: {migrated_count} users migrated from {ephemeral_path}")
                
            except Exception as e:
                print(f"❌ Migration error from {ephemeral_path}: {e}")

def ensure_schema_updates():
    """Ensure existing database has all required columns"""
    admin_db_path = os.path.join(PERSISTENT_DISK_PATH, 'admin_users.db')
    
    if os.path.exists(admin_db_path):
        conn = sqlite3.connect(admin_db_path)
        
        try:
            # Get current table schema
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add missing columns
            missing_columns = {
                'last_login': 'TIMESTAMP',
                'first_name': 'TEXT',
                'last_name': 'TEXT',
                'year_of_study': 'TEXT DEFAULT "1st"',
                'college': 'TEXT'
            }
            
            for column_name, column_type in missing_columns.items():
                if column_name not in columns:
                    print(f"🔧 Adding missing column: {column_name}")
                    conn.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                    conn.commit()
                    print(f"✅ Added column: {column_name}")
            
            print("✅ Schema updates completed")
            
        except Exception as e:
            print(f"❌ Schema update error: {e}")
        finally:
            conn.close()

def create_admin_users_database():
    """Create admin_users.db with complete schema"""
    admin_db_path = os.path.join(PERSISTENT_DISK_PATH, 'admin_users.db')
    
    print(f"📊 Creating admin_users.db at: {admin_db_path}")
    
    conn = sqlite3.connect(admin_db_path)
    
    # Main users table with ALL required columns
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            year_of_study TEXT DEFAULT '1st',
            college TEXT,
            user_type TEXT DEFAULT 'student',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Supporting tables for full QBank functionality
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            source_database TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, question_id, source_database)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            source_database TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_topic_completion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            source_database TEXT NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, subject, topic, source_database)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            questions_viewed INTEGER DEFAULT 0,
            answers_viewed INTEGER DEFAULT 0,
            topics_completed INTEGER DEFAULT 0,
            study_time_minutes INTEGER DEFAULT 0,
            databases_accessed TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    # Admin actions tracking table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            target_table TEXT,
            target_record_id INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ admin_users.db created with complete schema")

def create_qbank_databases():
    """Create QBank content databases if missing"""
    
    # Create 3rd_year.db with Anatomy content
    qbank_db_path = os.path.join(PERSISTENT_DISK_PATH, '3rd_year.db')
    if not os.path.exists(qbank_db_path):
        print("📚 Creating 3rd_year.db...")
        conn = sqlite3.connect(qbank_db_path)
        
        conn.execute('''
            CREATE TABLE qbank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                chapter TEXT,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                is_premium INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add comprehensive Anatomy questions
        anatomy_questions = [
            ('Anatomy', 'Basic Anatomy', 'What is the largest bone in the human body?', 'The femur (thigh bone) is the largest bone in the human body, extending from the hip to the knee.'),
            ('Anatomy', 'Cardiovascular System', 'Which chamber of the heart pumps blood to the lungs?', 'The right ventricle pumps blood to the lungs through the pulmonary artery for oxygenation.'),
            ('Anatomy', 'Nervous System', 'What is the basic functional unit of the nervous system?', 'The neuron is the basic functional unit of the nervous system, responsible for transmitting nerve impulses.'),
            ('Anatomy', 'Respiratory System', 'How many lobes does the right lung have?', 'The right lung has three lobes: upper (superior), middle, and lower (inferior) lobes.'),
            ('Anatomy', 'Musculoskeletal System', 'How many bones are there in an adult human body?', 'An adult human body has 206 bones, formed through the fusion of bones during development.'),
            ('Anatomy', 'Digestive System', 'What is the longest part of the small intestine?', 'The ileum is the longest part of the small intestine, measuring approximately 3.5 meters.'),
            ('Anatomy', 'Urinary System', 'Which kidney is typically located lower?', 'The right kidney is typically located slightly lower than the left kidney due to the liver.'),
            ('Anatomy', 'Endocrine System', 'Which gland is known as the master gland?', 'The pituitary gland is known as the master gland because it controls other endocrine glands.'),
            ('Anatomy', 'Reproductive System', 'How many chambers does the uterus have?', 'The uterus is a single-chambered organ, though it has three main parts: fundus, body, and cervix.'),
            ('Anatomy', 'Integumentary System', 'What is the largest organ of the human body?', 'The skin is the largest organ of the human body, covering the entire external surface.')
        ]
        
        for subject, topic, question, answer in anatomy_questions:
            conn.execute('''
                INSERT INTO qbank (subject, topic, question, answer) 
                VALUES (?, ?, ?, ?)
            ''', (subject, topic, question, answer))
        
        conn.commit()
        conn.close()
        print("✅ 3rd_year.db created with 10 Anatomy questions")
    
    # Create anatomy_mcq.db for multiple choice questions
    mcq_db_path = os.path.join(PERSISTENT_DISK_PATH, 'anatomy_mcq.db')
    if not os.path.exists(mcq_db_path):
        print("📝 Creating anatomy_mcq.db...")
        conn = sqlite3.connect(mcq_db_path)
        
        conn.execute('''
            CREATE TABLE mcq_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                chapter TEXT,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add comprehensive MCQ questions
        mcq_questions = [
            ('Anatomy', 'Basic Anatomy', 'Which is the longest bone in human body?', 'Humerus', 'Femur', 'Tibia', 'Radius', 'b', 'The femur (thigh bone) is the longest and strongest bone in the human body.'),
            ('Anatomy', 'Cardiovascular System', 'How many chambers does the human heart have?', '2', '3', '4', '5', 'c', 'The human heart has four chambers: two atria (left and right) and two ventricles (left and right).'),
            ('Anatomy', 'Nervous System', 'Which part of the brain controls balance?', 'Cerebrum', 'Cerebellum', 'Medulla', 'Pons', 'b', 'The cerebellum is responsible for balance, coordination, and fine motor control.'),
            ('Anatomy', 'Respiratory System', 'What is the voice box called?', 'Pharynx', 'Larynx', 'Trachea', 'Epiglottis', 'b', 'The larynx, commonly known as the voice box, contains the vocal cords.'),
            ('Anatomy', 'Digestive System', 'Which organ produces bile?', 'Pancreas', 'Gallbladder', 'Liver', 'Stomach', 'c', 'The liver produces bile, which is stored in the gallbladder and helps in fat digestion.'),
        ]
        
        for subject, topic, question, opt_a, opt_b, opt_c, opt_d, correct, explanation in mcq_questions:
            conn.execute('''
                INSERT INTO mcq_questions (subject, topic, question, option_a, option_b, option_c, option_d, correct_answer, explanation) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (subject, topic, question, opt_a, opt_b, opt_c, opt_d, correct, explanation))
        
        conn.commit()
        conn.close()
        print("✅ anatomy_mcq.db created with 5 MCQ questions")
    
    # Create general_mcq.db for general medical questions
    general_mcq_path = os.path.join(PERSISTENT_DISK_PATH, 'general_mcq.db')
    if not os.path.exists(general_mcq_path):
        print("🏥 Creating general_mcq.db...")
        conn = sqlite3.connect(general_mcq_path)
        
        conn.execute('''
            CREATE TABLE general_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                difficulty_level TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add general medical questions
        general_questions = [
            ('General Medicine', 'Basic Concepts', 'What is homeostasis?', 'Homeostasis is the process by which the body maintains stable internal conditions despite external changes.', 'basic'),
            ('General Medicine', 'Vital Signs', 'What is the normal heart rate range for adults?', 'The normal resting heart rate for adults is 60-100 beats per minute.', 'basic'),
            ('General Medicine', 'Medical Terminology', 'What does the prefix "hyper-" mean?', 'The prefix "hyper-" means excessive, above normal, or increased.', 'basic'),
        ]
        
        for subject, topic, question, answer, difficulty in general_questions:
            conn.execute('''
                INSERT INTO general_questions (subject, topic, question, answer, difficulty_level) 
                VALUES (?, ?, ?, ?, ?)
            ''', (subject, topic, question, answer, difficulty))
        
        conn.commit()
        conn.close()
        print("✅ general_mcq.db created with general medical questions")

def add_default_users(conn):
    """Add default admin and student accounts"""
    
    # Create system admin account
    admin_password = generate_password_hash('admin123')
    conn.execute('''
        INSERT OR REPLACE INTO users 
        (id, username, email, password, first_name, last_name, user_type, is_active, created_at) 
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('admin', 'admin@mbbsqbank.com', admin_password, 'Admin', 'User', 'admin', 1, 
          datetime.datetime.now().isoformat()))
    
    # Create your student account
    student_password = generate_password_hash('student123')
    conn.execute('''
        INSERT OR REPLACE INTO users 
        (id, username, email, password, first_name, last_name, user_type, is_active, created_at) 
        VALUES (2, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('priyanshuguha', 'priyanshu62@gmail.com', student_password, 'Priyanshu', 'Guha', 'student', 1, 
          datetime.datetime.now().isoformat()))
    
    print("✅ Default accounts created:")
    print("   Admin: admin@mbbsqbank.com / admin123")
    print("   Student: priyanshu62@gmail.com / student123")

def initialize_databases_on_startup():
    """Complete database initialization with error handling and migration"""
    
    print("🚀 Starting MBBS QBank database initialization...")
    print(f"📁 Using persistent storage path: {PERSISTENT_DISK_PATH}")
    
    # Ensure persistent storage directory exists
    os.makedirs(PERSISTENT_DISK_PATH, exist_ok=True)
    
    admin_db_path = os.path.join(PERSISTENT_DISK_PATH, 'admin_users.db')
    
    try:
        if os.path.exists(admin_db_path):
            print("📊 Existing admin_users.db found")
            
            # Check for ephemeral users to migrate
            migrate_ephemeral_users()
            
            # Ensure schema is up to date
            ensure_schema_updates()
            
            # Connect and verify essential users exist
            conn = sqlite3.connect(admin_db_path)
            
            # Check if system admin exists
            admin_exists = conn.execute(
                "SELECT COUNT(*) FROM users WHERE email = ?", 
                ('admin@mbbsqbank.com',)
            ).fetchone()[0]
            
            if admin_exists == 0:
                print("➕ Adding missing system admin account")
                admin_password = generate_password_hash('admin123')
                conn.execute('''
                    INSERT INTO users (username, email, password, first_name, last_name, user_type, is_active) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', ('admin', 'admin@mbbsqbank.com', admin_password, 'Admin', 'User', 'admin', 1))
                conn.commit()
            
            # Get user count
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            print(f"👥 Total users in database: {user_count}")
            
            conn.close()
            
        else:
            print("🆕 Creating fresh admin_users.db")
            
            # Create database with complete schema
            create_admin_users_database()
            
            # Add default users
            conn = sqlite3.connect(admin_db_path)
            add_default_users(conn)
            conn.commit()
            conn.close()
        
        # Create QBank content databases
        create_qbank_databases()
        
        # Final verification
        print("\n📋 Database initialization summary:")
        print(f"   📁 Persistent storage: {PERSISTENT_DISK_PATH}")
        print(f"   👥 User database: {'✅' if os.path.exists(admin_db_path) else '❌'}")
        print(f"   📚 QBank database: {'✅' if os.path.exists(os.path.join(PERSISTENT_DISK_PATH, '3rd_year.db')) else '❌'}")
        print(f"   📝 MCQ database: {'✅' if os.path.exists(os.path.join(PERSISTENT_DISK_PATH, 'anatomy_mcq.db')) else '❌'}")
        
        print("✅ MBBS QBank database initialization completed successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise e

if __name__ == "__main__":
    initialize_databases_on_startup()
