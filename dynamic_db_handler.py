# dynamic_db_handler.py - COMPLETE VERSION WITH CENTRALIZED USER MANAGEMENT
import sqlite3
import os
import glob
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime
import shutil
import traceback
from werkzeug.utils import secure_filename


class DynamicDatabaseHandler:
    def __init__(self):
        self.persistent_path = os.environ.get('RENDER_PERSISTENT_DISK_PATH', '/opt/render/project/data')

        os.makedirs(self.persistent_path, exist_ok=True)

        self.db_categories = {
            'qbank': {
                'pattern': '*year*.db',
                'description': 'Question Bank Databases',
                'required_tables': ['qbank'],
                'schema': self.get_qbank_schema()
            },
            'users': {
                'pattern': 'admin_users.db',
                'description': 'Centralized User Database',
                'required_tables': ['users'],
                'schema': self.get_centralized_user_schema()
            },
            'mcq': {
                'pattern': '*mcq*.db',
                'description': 'MCQ Databases',
                'required_tables': ['mcq_questions'],
                'schema': self.get_mcq_schema()
            },
            'admin': {
                'pattern': 'admin*.db',
                'description': 'Admin & System Data',
                'required_tables': ['admin_actions'],
                'schema': self.get_admin_schema()
            },
            # ------ Add this block ------
            'test': {
                'pattern': '*test*.db',
                'description': 'Test Databases',
                'required_tables': ['test_info', 'test_questions'],
                'schema': self.get_test_schema()
            }
            # ------ End addition ------
        }

    def get_test_schema(self):
        """Schema for test-type databases with subjects, topics, MCQs, and timing info"""
        return {
            'test_info': '''
                CREATE TABLE IF NOT EXISTS test_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    description TEXT,
                    duration_minutes INTEGER NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'test_questions': '''
                CREATE TABLE IF NOT EXISTS test_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_answer TEXT NOT NULL, -- one of 'a', 'b', 'c', 'd'
                    FOREIGN KEY (test_id) REFERENCES test_info (id)
                )
            ''',
            'test_results': '''
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    user_id INTEGER,
                    score INTEGER,
                    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (test_id) REFERENCES test_info (id)
                )
            '''
        }

    def get_qbank_schema(self):
        """Example schema for question bank"""
        return {
            'qbank': '''
                CREATE TABLE IF NOT EXISTS qbank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    year INTEGER,
                    subject TEXT,
                    topic TEXT
                )
            '''
        }

    def get_centralized_user_schema(self):
        """Example schema for user database"""
        return {
            'users': '''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }

    def get_mcq_schema(self):
        """Example schema for MCQ questions"""
        return {
            'mcq_questions': '''
                CREATE TABLE IF NOT EXISTS mcq_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct_answer TEXT NOT NULL -- one of 'a', 'b', 'c', 'd'
                )
            '''
        }

    def get_admin_schema(self):
        """Example schema for admin/system data"""
        return {
            'admin_actions': '''
                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    performed_by TEXT,
                    action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            '''
        }

        # Auto-discover databases on startup
        self.discovered_databases = self.discover_databases()

    # Add the schema getter just below
    
    def discover_databases(self):
    
        discovered = {}
        
        for category, config in self.db_categories.items():
            discovered[category] = []
            
            # Search in persistent disk path instead of current directory
            pattern_path = os.path.join(self.persistent_path, config['pattern'])
            matching_files = glob.glob(pattern_path)
            
            for db_file in matching_files:
                if os.path.exists(db_file):
                    db_info = {
                        'file': db_file,  # Keep full path
                        'name': os.path.splitext(os.path.basename(db_file))[0],
                        'size': os.path.getsize(db_file),
                        'modified': datetime.fromtimestamp(os.path.getmtime(db_file))
                    }
                    discovered[category].append(db_info)
        
        return discovered

    
    def get_connection(self, db_file):
    
        import os
        
        # Handle different input formats
        if os.path.isabs(db_file):
            full_path = db_file
        else:
            basename = os.path.basename(db_file)
            full_path = os.path.join(self.persistent_path, basename)
        
        # Verify file exists
        if not os.path.exists(full_path):
            available = []
            try:
                available = [f for f in os.listdir(self.persistent_path) if f.endswith('.db')]
            except:
                pass
            raise FileNotFoundError(f"Database file {os.path.basename(full_path)} not found. Available: {available}")
        
        conn = sqlite3.connect(full_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    
    def safe_table_name(self, table_name):
        """Safely quote table names for SQL queries"""
        # Remove any existing quotes and add double quotes
        clean_name = table_name.strip('"').strip("'").strip("`").strip("[").strip("]")
        return f'"{clean_name}"'
    
    def table_exists(self, conn, table_name):
        """Check if a table exists in the database"""
        result = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name = ?
        """, (table_name,)).fetchone()
        return result is not None
    
    def get_qbank_schema(self):
        """Schema for qbank-type databases - CONTENT ONLY (no user tables)"""
        return {
            'qbank': '''
                CREATE TABLE IF NOT EXISTS qbank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    chapter TEXT,
                    topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    is_premium INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }
    
    def get_centralized_user_schema(self):
        """Schema for centralized user database - ALL USER DATA"""
        return {
            'users': '''
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
            ''',
            'user_bookmarks': '''
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
            ''',
            'user_notes': '''
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
            ''',
            'user_topic_completion': '''
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
            ''',
            'user_analytics': '''
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
            '''
        }
    
    def get_mcq_schema(self):
        """Schema for MCQ-type databases"""
        return {
            'mcq_questions': '''
                CREATE TABLE IF NOT EXISTS mcq_questions (
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
                    difficulty TEXT DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'mcq_tests': '''
                CREATE TABLE IF NOT EXISTS mcq_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    test_name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    total_questions INTEGER NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'mcq_results': '''
                CREATE TABLE IF NOT EXISTS mcq_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    test_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    percentage REAL NOT NULL,
                    time_taken_minutes INTEGER NOT NULL,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }
    
    def get_admin_schema(self):
        """Schema for admin/system data databases"""
        return {
            'admin_actions': '''
                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_db TEXT,
                    target_table TEXT,
                    action_details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'system_settings': '''
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'database_migrations': '''
                CREATE TABLE IF NOT EXISTS database_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT NOT NULL,
                    source_database TEXT,
                    target_database TEXT,
                    records_migrated INTEGER DEFAULT 0,
                    migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed'
                )
            '''
        }
    
    def add_new_database(self, category, db_name):
        """Add a new database to a category in persistent storage"""
        if category not in self.db_categories:
            return False, "Invalid category"
        
        # Create database file name based on category
        if category == 'qbank':
            db_file = f"{db_name}_year.db"
        elif category == 'mcq':
            db_file = f"{db_name}_mcq.db"  
        elif category == 'admin':
            db_file = f"admin_{db_name}.db"
        elif category == 'users':
            db_file = "admin_users.db"
        else:
            db_file = f"{db_name}.db"
        
        # CREATE IN PERSISTENT STORAGE PATH
        full_path = os.path.join(self.persistent_path, db_file)
        
        # Check if database already exists
        if os.path.exists(full_path):
            return False, f"Database {db_file} already exists"
        
        try:
            # Create database with proper schema
            conn = sqlite3.connect(full_path)  # ✅ Use persistent path
            schema = self.db_categories[category]['schema']
            
            for table_name, create_sql in schema.items():
                conn.execute(create_sql)
            
            conn.commit()
            conn.close()
            
            # Refresh discovered databases
            self.discovered_databases = self.discover_databases()
            
            return True, f"Database {db_file} created successfully"
        
        except Exception as e:
            return False, f"Error creating database: {str(e)}"

    def upload_database(self, uploaded_file, category):
    
        if not uploaded_file or uploaded_file.filename == '':
            return False, "No file selected"
        
        filename = secure_filename(uploaded_file.filename)
        
        if not filename.lower().endswith('.db'):
            return False, "File must have .db extension"
        
        # CREATE FULL PATH IN PERSISTENT STORAGE
        full_path = os.path.join(self.persistent_path, filename)
        
        if category == 'users' and filename != 'admin_users.db':
            return False, "User database must be named 'admin_users.db'"
        
        # Check if file already exists in persistent storage
        if os.path.exists(full_path):
            return False, f"Database {filename} already exists"
        
        try:
            # Save the uploaded file to persistent storage
            uploaded_file.save(full_path)  # ✅ Save to persistent path
            
            # Validate it's a proper SQLite database
            conn = sqlite3.connect(full_path)  # ✅ Connect to persistent path
            
            # Rest of validation logic...
            required_tables = self.db_categories[category]['required_tables']
            
            for table in required_tables:
                result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name = ?
                """, (table,)).fetchone()
                
                if not result:
                    conn.close()
                    os.remove(full_path)  # ✅ Remove from persistent path
                    return False, f"Database missing required table: {table}"
            
            conn.close()
            self.discovered_databases = self.discover_databases()
            
            return True, f"Database {filename} uploaded successfully"
            
        except Exception as e:
            if os.path.exists(full_path):
                os.remove(full_path)  # ✅ Clean up persistent path
            return False, f"Error uploading database: {str(e)}"

    
    def get_database_stats(self, db_file):
        """Get statistics for a database with better error handling"""
        try:
            conn = self.get_connection(db_file)
            
            # Get all tables
            tables = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """).fetchall()
            
            stats = {
                'file': db_file,
                'tables': [],
                'total_records': 0
            }
            
            for table in tables:
                table_name = table['name']
                try:
                    safe_name = self.safe_table_name(table_name)
                    count_query = f"SELECT COUNT(*) as count FROM {safe_name}"
                    count = conn.execute(count_query).fetchone()['count']
                    
                    stats['tables'].append({
                        'name': table_name,
                        'records': count
                    })
                    stats['total_records'] += count
                except Exception as e:
                    print(f"Error counting records in table {table_name}: {e}")
                    stats['tables'].append({
                        'name': table_name,
                        'records': 0,
                        'error': str(e)
                    })
            
            conn.close()
            return stats
        
        except Exception as e:
            return {'error': str(e)}
    
    def backup_all_databases(self):
        """Backup all discovered databases"""
        try:
            backup_dir = f"backups/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_count = 0
            for category, databases in self.discovered_databases.items():
                category_dir = os.path.join(backup_dir, category)
                os.makedirs(category_dir, exist_ok=True)
                
                for db_info in databases:
                    source_file = db_info['file']
                    dest_file = os.path.join(category_dir, os.path.basename(source_file))
                    shutil.copy2(source_file, dest_file)
                    backup_count += 1
            
            return True, f"Successfully backed up {backup_count} databases to {backup_dir}"
        
        except Exception as e:
            return False, f"Backup failed: {str(e)}"
    
    def migrate_users_to_centralized_db(self):
    
        try:
            # ✅ FIXED - Use persistent storage path
            centralized_db_path = os.path.join(self.persistent_path, 'admin_users.db')
            
            if not os.path.exists(centralized_db_path):
                success, message = self.add_new_database('users', 'centralized')
                if not success:
                    return False, f"Failed to create centralized user database: {message}"
            
            centralized_conn = self.get_connection('admin_users.db')
        # Rest of function remains the same...


            migration_count = 0
            
            # Migrate from all QBank databases
            qbank_databases = self.discovered_databases.get('qbank', [])
            
            for db_info in qbank_databases:
                db_file = db_info['file']
                print(f"Migrating users from {db_file}...")
                
                try:
                    source_conn = self.get_connection(db_file)
                    
                    # Check if source database has users table
                    if not self.table_exists(source_conn, 'users'):
                        source_conn.close()
                        continue
                    
                    # Migrate users (avoid duplicates by email)
                    users = source_conn.execute('SELECT * FROM users').fetchall()
                    for user in users:
                        try:
                            centralized_conn.execute('''
                                INSERT OR IGNORE INTO users 
                                (username, email, password, created_at)
                                VALUES (?, ?, ?, ?)
                            ''', (user['username'], user['email'], user['password'], user['created_at']))
                            migration_count += 1
                        except Exception as e:
                            print(f"User migration error: {e}")
                    
                    # Migrate bookmarks if they exist
                    if self.table_exists(source_conn, 'bookmarks'):
                        bookmarks = source_conn.execute('SELECT * FROM bookmarks').fetchall()
                        for bookmark in bookmarks:
                            try:
                                centralized_conn.execute('''
                                    INSERT OR IGNORE INTO user_bookmarks 
                                    (user_id, question_id, subject, topic, source_database, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (bookmark['user_id'], bookmark['question_id'], 
                                      bookmark['subject'], bookmark['topic'], db_file, bookmark['created_at']))
                            except Exception as e:
                                print(f"Bookmark migration error: {e}")
                    
                    source_conn.close()
                    
                except Exception as e:
                    print(f"Error migrating from {db_file}: {e}")
            
            centralized_conn.commit()
            centralized_conn.close()
            
            # Refresh discovered databases
            self.discovered_databases = self.discover_databases()
            
            return True, f"Successfully migrated {migration_count} user records to admin_users.db"
            
        except Exception as e:
            return False, f"Migration failed: {str(e)}"


# Global instance
dynamic_db_handler = DynamicDatabaseHandler()


# CENTRALIZED USER MANAGEMENT FUNCTIONS
def create_centralized_user_database():
    """Create admin_users.db as the ONLY user database for the entire system"""
    return dynamic_db_handler.add_new_database('users', 'centralized')


def migrate_all_users_to_centralized_db():
    """Migrate ALL users from ALL databases to admin_users.db"""
    return dynamic_db_handler.migrate_users_to_centralized_db()


# INTEGRATION FUNCTIONS FOR APP.PY
def get_all_qbank_subjects():
    """Get all subjects from all discovered QBank databases"""
    all_subjects = {}
    
    # Refresh discovery first
    dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
    
    # Get all QBank databases
    qbank_databases = dynamic_db_handler.discovered_databases.get('qbank', [])
    
    for db_info in qbank_databases:
        db_file = db_info['file']
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            
            # Get subjects from this database
            subjects = conn.execute('''
                SELECT DISTINCT subject, COUNT(*) as question_count
                FROM qbank 
                GROUP BY subject 
                ORDER BY subject
            ''').fetchall()
            
            for subject_row in subjects:
                subject = subject_row['subject']
                if subject not in all_subjects:
                    all_subjects[subject] = []
                
                all_subjects[subject].append({
                    'database': db_file,
                    'question_count': subject_row['question_count']
                })
            
            conn.close()
        except Exception as e:
            print(f"Error reading subjects from {db_file}: {e}")
    
    return all_subjects


def find_subject_database(subject_name):
    """Find which database contains a specific subject"""
    # Refresh discovery
    dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
    
    qbank_databases = dynamic_db_handler.discovered_databases.get('qbank', [])
    
    for db_info in qbank_databases:
        db_file = db_info['file']
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            
            # Check if subject exists in this database
            result = conn.execute('''
                SELECT COUNT(*) as count 
                FROM qbank 
                WHERE LOWER(subject) = ?
            ''', (subject_name.lower(),)).fetchone()
            
            conn.close()
            
            if result['count'] > 0:
                return db_file
        except Exception as e:
            print(f"Error checking subject in {db_file}: {e}")
    
    # Default fallback
    return '1st_year.db'


def register_dynamic_db_routes(app, ensure_user_session_func):
    """Register dynamic database management routes with centralized user support"""
    
    @app.route('/admin/dynamic_db_manager')
    def dynamic_db_home():
        """Main dynamic database manager interface"""
        # Refresh database discovery
        dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
        
        # Get stats for each discovered database
        db_stats = {}
        for category, databases in dynamic_db_handler.discovered_databases.items():
            db_stats[category] = []
            for db_info in databases:
                stats = dynamic_db_handler.get_database_stats(db_info['file'])
                if 'error' not in stats:
                    db_stats[category].append({**db_info, **stats})
                else:
                    db_stats[category].append({**db_info, 'error': stats['error']})
        
        return render_template('dynamic_db_manager.html', 
                             categories=dynamic_db_handler.db_categories,
                             discovered_databases=dynamic_db_handler.discovered_databases,
                             db_stats=db_stats)
    
    @app.route('/admin/add_database', methods=['GET', 'POST'])
    def add_new_database():
        """Add a new database"""
        if request.method == 'POST':
            category = request.form['category']
            db_name = request.form['db_name'].strip()
            
            if not db_name:
                flash('Database name is required', 'error')
                return redirect(url_for('add_new_database'))
            
            success, message = dynamic_db_handler.add_new_database(category, db_name)
            
            if success:
                flash(message, 'success')
                return redirect(url_for('dynamic_db_home'))
            else:
                flash(message, 'error')
        
        return render_template('add_database.html', 
                             categories=dynamic_db_handler.db_categories)
    
    @app.route('/admin/upload_database', methods=['GET', 'POST'])
    def upload_database():
        """Upload an existing database file"""
        if request.method == 'POST':
            # Check if file was uploaded
            if 'database_file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['database_file']
            category = request.form.get('category')
            
            if not category:
                flash('Please select a database category', 'error')
                return redirect(request.url)
            
            # Upload and validate the database
            success, message = dynamic_db_handler.upload_database(file, category)
            
            if success:
                flash(message, 'success')
                return redirect(url_for('dynamic_db_home'))
            else:
                flash(message, 'error')
        
        return render_template('upload_database.html', 
                             categories=dynamic_db_handler.db_categories)
    
    @app.route('/admin/migrate_users')
    def migrate_users():
        """Migrate users from all databases to centralized admin_users.db"""
        success, message = dynamic_db_handler.migrate_users_to_centralized_db()
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('dynamic_db_home'))
    
    @app.route('/admin/manage_db/<db_file>')
    def manage_specific_database(db_file):
        """Manage a specific database with better error handling"""
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            
            # Get all tables
            tables = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """).fetchall()
            
            # Get table statistics
            table_stats = []
            for table in tables:
                table_name = table['name']
                try:
                    safe_name = dynamic_db_handler.safe_table_name(table_name)
                    count_query = f"SELECT COUNT(*) as count FROM {safe_name}"
                    count = conn.execute(count_query).fetchone()['count']
                    
                    # Get column info
                    columns = conn.execute(f"PRAGMA table_info({safe_name})").fetchall()
                    
                    table_stats.append({
                        'name': table_name,
                        'records': count,
                        'columns': len(columns)
                    })
                except Exception as e:
                    print(f"Error getting stats for table {table_name}: {e}")
                    table_stats.append({
                        'name': table_name,
                        'records': 0,
                        'columns': 0,
                        'error': str(e)
                    })
            
            conn.close()
            
            return render_template('manage_database.html',
                                 db_file=db_file,
                                 tables=table_stats)
        
        except Exception as e:
            flash(f'Error accessing database: {str(e)}', 'error')
            return redirect(url_for('dynamic_db_home'))
    
    @app.route('/admin/edit_table/<db_file>/<table_name>')
    def edit_database_table(db_file, table_name):
        """FIXED: Edit a specific table in a database with proper SQL handling"""
        try:
            print(f"Attempting to edit table: {table_name} in database: {db_file}")
            
            conn = dynamic_db_handler.get_connection(db_file)
            
            # Check if table exists first
            if not dynamic_db_handler.table_exists(conn, table_name):
                flash(f'Table "{table_name}" does not exist in database', 'error')
                conn.close()
                return redirect(url_for('manage_specific_database', db_file=db_file))
            
            # Get table schema using safe table name
            safe_name = dynamic_db_handler.safe_table_name(table_name)
            try:
                schema = conn.execute(f"PRAGMA table_info({safe_name})").fetchall()
                print(f"Schema retrieved: {len(schema)} columns")
            except Exception as e:
                print(f"Error getting schema: {e}")
                flash(f'Error getting table schema: {str(e)}', 'error')
                conn.close()
                return redirect(url_for('manage_specific_database', db_file=db_file))
            
            if not schema:
                flash(f'Table "{table_name}" has no accessible schema', 'error')
                conn.close()
                return redirect(url_for('manage_specific_database', db_file=db_file))
            
            # Get table data with pagination
            page = request.args.get('page', 1, type=int)
            per_page = 25
            offset = (page - 1) * per_page
            
            try:
                # Use COALESCE to handle potential NULL id values
                data_query = f"""
                    SELECT * FROM {safe_name} 
                    ORDER BY COALESCE(id, 0) DESC
                    LIMIT ? OFFSET ?
                """
                data = conn.execute(data_query, (per_page, offset)).fetchall()
                print(f"Data retrieved: {len(data)} records")
                
                # Get total count
                count_query = f"SELECT COUNT(*) as count FROM {safe_name}"
                total = conn.execute(count_query).fetchone()['count']
                print(f"Total records: {total}")
                
            except Exception as e:
                print(f"Error retrieving table data: {e}")
                flash(f'Error retrieving table data: {str(e)}', 'error')
                conn.close()
                return redirect(url_for('manage_specific_database', db_file=db_file))
            
            conn.close()
            
            return render_template('edit_table.html',
                                 db_file=db_file,
                                 table_name=table_name,
                                 schema=schema,
                                 data=data,
                                 page=page,
                                 total=total,
                                 per_page=per_page)
        
        except Exception as e:
            print(f"Critical error in edit_database_table: {str(e)}")
            print(traceback.format_exc())
            flash(f'Critical error accessing table: {str(e)}', 'error')
            return redirect(url_for('manage_specific_database', db_file=db_file))
    
    @app.route('/admin/edit_record/<db_file>/<table_name>/<int:record_id>', methods=['GET', 'POST'])
    def edit_database_record(db_file, table_name, record_id):
        """FIXED: Edit a specific record with robust error handling"""
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            safe_name = dynamic_db_handler.safe_table_name(table_name)
            
            if request.method == 'POST':
                # Log admin action
                admin_user_id = session.get('user_id', 'anonymous')
                
                # Build update query safely
                updates = []
                values = []
                for key, value in request.form.items():
                    if key not in ['csrf_token', 'submit']:
                        safe_column = dynamic_db_handler.safe_table_name(key)
                        updates.append(f"{safe_column} = ?")
                        values.append(value)
                
                if updates:
                    values.append(record_id)
                    update_query = f'UPDATE {safe_name} SET {", ".join(updates)} WHERE id = ?'
                    print(f"Executing update query: {update_query}")
                    print(f"With values: {values}")
                    
                    conn.execute(update_query, values)
                    
                    # Log the action (try to add to admin_actions if it exists)
                    try:
                        if dynamic_db_handler.table_exists(conn, 'admin_actions'):
                            conn.execute('''
                                INSERT INTO admin_actions (admin_user_id, action_type, target_db, target_table, action_details)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (str(admin_user_id), 'UPDATE', db_file, table_name, f'Updated record ID {record_id}'))
                    except Exception as log_error:
                        print(f"Could not log admin action: {log_error}")
                    
                    conn.commit()
                    flash('Record updated successfully!', 'success')
                    conn.close()
                    return redirect(url_for('edit_database_table', db_file=db_file, table_name=table_name))
            
            # GET request - get record and schema
            record_query = f'SELECT * FROM {safe_name} WHERE id = ?'
            record = conn.execute(record_query, (record_id,)).fetchone()
            
            if not record:
                flash('Record not found', 'error')
                conn.close()
                return redirect(url_for('edit_database_table', db_file=db_file, table_name=table_name))
            
            schema = conn.execute(f'PRAGMA table_info({safe_name})').fetchall()
            conn.close()
            
            return render_template('edit_record.html',
                                 db_file=db_file,
                                 table_name=table_name,
                                 record=record,
                                 schema=schema)
        
        except Exception as e:
            print(f"Error in edit_database_record: {str(e)}")
            print(traceback.format_exc())
            flash(f'Error editing record: {str(e)}', 'error')
            return redirect(url_for('edit_database_table', db_file=db_file, table_name=table_name))
                    
                    # 1. Insert a new test into test_info





    @app.route('/admin/add_record/<db_file>/<table_name>', methods=['GET', 'POST'])
    def add_database_record(db_file, table_name):
        """FIXED: Add a new record to a table"""
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            safe_name = dynamic_db_handler.safe_table_name(table_name)
            
            if request.method == 'POST':
                admin_user_id = session.get('user_id', 'anonymous')
                
                # Build insert query safely
                columns = []
                values = []
                placeholders = []
                
                for key, value in request.form.items():
                    if key not in ['csrf_token', 'submit'] and value.strip():
                        safe_column = dynamic_db_handler.safe_table_name(key)
                        columns.append(safe_column)
                        values.append(value)
                        placeholders.append('?')
                
                if columns:
                    insert_query = f"INSERT INTO {safe_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    print(f"Executing insert query: {insert_query}")
                    print(f"With values: {values}")
                    
                    cursor = conn.execute(insert_query, values)
                    
                    # Log the action
                    try:
                        if dynamic_db_handler.table_exists(conn, 'admin_actions'):
                            conn.execute('''
                                INSERT INTO admin_actions (admin_user_id, action_type, target_db, target_table, action_details)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (str(admin_user_id), 'INSERT', db_file, table_name, f'Added new record ID {cursor.lastrowid}'))
                    except Exception as log_error:
                        print(f"Could not log admin action: {log_error}")
                    
                    conn.commit()
                    flash('Record added successfully!', 'success')
                    conn.close()
                    return redirect(url_for('edit_database_table', db_file=db_file, table_name=table_name))
                else:
                    flash('Please fill at least one field', 'error')
            
            # GET request - get schema for form
            schema = conn.execute(f'PRAGMA table_info({safe_name})').fetchall()
            conn.close()
            
            return render_template('add_record.html',
                                 db_file=db_file,
                                 table_name=table_name,
                                 schema=schema)
        
        except Exception as e:
            print(f"Error in add_database_record: {str(e)}")
            print(traceback.format_exc())
            flash(f'Error adding record: {str(e)}', 'error')
            return redirect(url_for('edit_database_table', db_file=db_file, table_name=table_name))
    
    @app.route('/admin/database_backup')
    def backup_all_databases():
        """Backup all discovered databases"""
        success, message = dynamic_db_handler.backup_all_databases()
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('dynamic_db_home'))
    
    @app.route('/admin/delete_database/<db_file>', methods=['POST'])
    def delete_database(db_file):
        """Delete a database (with confirmation)"""
        try:
            if db_file == 'admin_users.db':
                flash('Cannot delete centralized user database!', 'error')
                return redirect(url_for('dynamic_db_home'))
            
            # ✅ FIXED - Ensure proper path resolution
            if os.path.isabs(db_file):
                full_path = os.path.join(dynamic_db_handler.persistent_path, os.path.basename(db_file))
            else:
                full_path = os.path.join(dynamic_db_handler.persistent_path, db_file)
            
            if os.path.exists(full_path):
                # ✅ FIXED - Create backup in persistent storage
                backup_base_dir = os.path.join(dynamic_db_handler.persistent_path, 'deleted_backups')
                backup_dir = os.path.join(backup_base_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
                os.makedirs(backup_dir, exist_ok=True)
            
            # Rest of function remains the same...

                shutil.copy2(full_path, os.path.join(backup_dir, os.path.basename(full_path)))
                
                # Delete the database from persistent storage
                os.remove(full_path)  # ✅ Remove from persistent path
                
                dynamic_db_handler.discovered_databases = dynamic_db_handler.discover_databases()
                
                flash(f'Database {os.path.basename(db_file)} deleted successfully. Backup saved to {backup_dir}', 'success')
            else:
                flash('Database file not found in persistent storage', 'error')
        
        except Exception as e:
            flash(f'Error deleting database: {str(e)}', 'error')
        
        return redirect(url_for('dynamic_db_home'))

    
    @app.route('/admin/debug_table/<db_file>/<table_name>')
    def debug_table_access(db_file, table_name):
        """Debug function to diagnose table access issues"""
        try:
            conn = dynamic_db_handler.get_connection(db_file)
            
            # Check if table exists
            exists = dynamic_db_handler.table_exists(conn, table_name)
            
            # Get all tables in database
            all_tables = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """).fetchall()
            
            table_list = [t['name'] for t in all_tables]
            
            if not exists:
                conn.close()
                return f"""
                <h2>Debug: Table '{table_name}' NOT FOUND in {db_file}</h2>
                <p><strong>Available tables:</strong> {', '.join(table_list)}</p>
                <p><a href="{url_for('manage_specific_database', db_file=db_file)}">Back to Database</a></p>
                """
            
            # Get schema
            safe_name = dynamic_db_handler.safe_table_name(table_name)
            schema = conn.execute(f"PRAGMA table_info({safe_name})").fetchall()
            
            # Try to count records
            try:
                count_query = f"SELECT COUNT(*) as count FROM {safe_name}"
                count = conn.execute(count_query).fetchone()['count']
            except Exception as e:
                count = f"Error counting: {e}"
            
            # Try to get sample data
            try:
                sample_query = f"SELECT * FROM {safe_name} LIMIT 3"
                sample_data = conn.execute(sample_query).fetchall()
                sample_info = f"Sample records retrieved: {len(sample_data)}"
            except Exception as e:
                sample_info = f"Error getting sample data: {e}"
            
            conn.close()
            
            return f"""
            <h2>Debug Info for '{table_name}' in {db_file}</h2>
            <p><strong>Table exists:</strong> ✅ Yes</p>
            <p><strong>Safe table name:</strong> {safe_name}</p>
            <p><strong>Schema columns:</strong> {len(schema)}</p>
            <p><strong>Record count:</strong> {count}</p>
            <p><strong>Sample data:</strong> {sample_info}</p>
            <p><strong>All tables in DB:</strong> {', '.join(table_list)}</p>
            <h3>Schema Details:</h3>
            <ul>
            {''.join([f'<li>{col[1]} ({col[2]}) - NOT NULL: {bool(col[3])}</li>' for col in schema])}
            </ul>
            <p><a href="{url_for('edit_database_table', db_file=db_file, table_name=table_name)}">Try Edit Table</a> | 
               <a href="{url_for('manage_specific_database', db_file=db_file)}">Back to Database</a></p>
            """
            
        except Exception as e:
            return f"""
            <h2>Debug Error for '{table_name}' in {db_file}</h2>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><strong>Traceback:</strong></p>
            <pre>{traceback.format_exc()}</pre>
            <p><a href="{url_for('manage_specific_database', db_file=db_file)}">Back to Database</a></p>
            """
