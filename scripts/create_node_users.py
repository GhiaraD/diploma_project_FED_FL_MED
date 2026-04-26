#!/usr/bin/env python3
"""
Create admin users for node2 and node3
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'node', 'api'))

from app.database import get_db
from app.security import SecurityManager
from sqlalchemy import text
import uuid

def create_user(node_id: str, email: str, password: str):
    """Create an admin user for a node."""
    db = next(get_db())
    security = SecurityManager()
    
    try:
        # Check if user already exists
        result = db.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if result:
            print(f"User {email} already exists")
            return
        
        # Create new user
        user_id = str(uuid.uuid4())
        password_hash = security.get_password_hash(password)
        
        db.execute(
            text("""
                INSERT INTO users (user_id, email, password_hash, role, node_id, is_active)
                VALUES (:user_id, :email, :password_hash, :role, :node_id, :is_active)
            """),
            {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "role": "admin",
                "node_id": node_id,
                "is_active": 1
            }
        )
        
        db.commit()
        print(f"✅ Created admin user for {node_id}: {email}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user {email}: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("Creating admin users for node2 and node3...")
    print()
    
    # Node 2
    create_user("node2", "admin@node2.fed-med-fl.com", "AdminNode2@2026")
    
    # Node 3
    create_user("node3", "admin@node3.fed-med-fl.com", "AdminNode3@2026")
    
    print()
    print("Done!")
