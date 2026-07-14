import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_path="escrow.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Escrows table with all fields
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS escrows (
                escrow_id TEXT PRIMARY KEY,
                buyer_id INTEGER,
                seller_id INTEGER,
                seller_username TEXT,
                seller_address TEXT,
                currency TEXT,
                amount REAL,
                fee REAL,
                total_amount REAL,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        self.conn.commit()
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def create_escrow(self, escrow_id, buyer_id, seller_id, seller_username, seller_address, currency, amount, fee):
        total = amount + fee
        self.cursor.execute('''
            INSERT INTO escrows (
                escrow_id, buyer_id, seller_id, seller_username, seller_address,
                currency, amount, fee, total_amount, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (escrow_id, buyer_id, seller_id, seller_username, seller_address,
              currency, amount, fee, total, 'pending'))
        self.conn.commit()
        return escrow_id
    
    def update_escrow_status(self, escrow_id, status):
        self.cursor.execute('''
            UPDATE escrows SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE escrow_id = ?
        ''', (status, escrow_id))
        self.conn.commit()
    
    def get_escrow(self, escrow_id):
        self.cursor.execute('SELECT * FROM escrows WHERE escrow_id = ?', (escrow_id,))
        return self.cursor.fetchone()
    
    def get_user_escrows(self, user_id):
        self.cursor.execute('''
            SELECT * FROM escrows 
            WHERE buyer_id = ? OR seller_id = ?
            ORDER BY created_at DESC
        ''', (user_id, user_id))
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()