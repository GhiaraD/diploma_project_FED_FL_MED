#!/usr/bin/env python3
"""
Initialize security for Fed-Med-FL platform - Local version.

Creates database tables and default users for each node.
"""
import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import secrets
import json
import bcrypt

def get_password_hash(password: str) -> str:
    """Generate password hash using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_default_users():
    """Create default users for each node."""
    
    # Connect to each node's database
    nodes = ['node1', 'node2', 'node3']
    
    for node in nodes:
        db_path = f"storage/{node}/node.db"
        
        if not os.path.exists(f"storage/{node}"):
            os.makedirs(f"storage/{node}", exist_ok=True)
        
        print(f"\n🔧 Setting up security for {node}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Create users table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP,
                    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create api_keys table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    key_hash TEXT UNIQUE NOT NULL,
                    node_id TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    created_by TEXT
                )
            ''')
            
            # Create audit_logs table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    node_id TEXT NOT NULL,
                    endpoint TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    request_id TEXT,
                    response_status INTEGER,
                    duration_ms INTEGER,
                    details TEXT
                )
            ''')
            
            # Default users for this node
            default_users = [
                {
                    "email": f"admin@{node}.fed-med-fl.com",
                    "password": f"Admin{node.capitalize()}@2026",
                    "role": "admin",
                    "node_id": node
                },
                {
                    "email": f"doctor@{node}.fed-med-fl.com", 
                    "password": f"Doctor{node.capitalize()}@2026",
                    "role": "doctor",
                    "node_id": node
                },
                {
                    "email": f"researcher@{node}.fed-med-fl.com",
                    "password": f"Researcher{node.capitalize()}@2026", 
                    "role": "researcher",
                    "node_id": node
                }
            ]
            
            # Add viewer user only to node1
            if node == "node1":
                default_users.append({
                    "email": "viewer@fed-med-fl.com",
                    "password": "ViewerAccess@2026",
                    "role": "viewer", 
                    "node_id": "node1"
                })
            
            for user_data in default_users:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (user_data["email"],))
                if cursor.fetchone():
                    print(f"⚠️  User {user_data['email']} already exists, skipping...")
                    continue
                
                # Create user
                user_id = f"user_{secrets.token_hex(8)}"
                hashed_password = get_password_hash(user_data["password"])
                
                cursor.execute('''
                    INSERT INTO users (id, email, password_hash, role, node_id, is_active, created_at, password_changed_at, failed_login_attempts)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, 0)
                ''', (
                    user_id,
                    user_data["email"],
                    hashed_password,
                    user_data["role"],
                    user_data["node_id"],
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))
                
                print(f"✅ Created user: {user_data['email']} ({user_data['role']} @ {user_data['node_id']})")
            
            # Create API key for this node
            cursor.execute("SELECT id FROM api_keys WHERE node_id = ?", (node,))
            if not cursor.fetchone():
                api_key = f"fed_med_fl_{node}_{secrets.token_urlsafe(32)}"
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                
                permissions = ["federated:participate", "central:register", "inter_node:communicate"]
                if node == "central":
                    permissions = ["*"]  # Central has full permissions
                
                cursor.execute('''
                    INSERT INTO api_keys (id, key_hash, node_id, permissions, expires_at, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                ''', (
                    f"key_{secrets.token_hex(8)}",
                    key_hash,
                    node,
                    json.dumps(permissions),
                    (datetime.utcnow() + timedelta(days=3650)).isoformat(),  # 10 years
                    datetime.utcnow().isoformat()
                ))
                
                print(f"✅ Created API key for {node}")
                print(f"   Key: {api_key}")
                
                # Save key to file
                key_file = Path(f"storage/{node}_api_key.txt")
                with open(key_file, 'w') as f:
                    f.write(f"# API Key for {node}\n")
                    f.write(f"# Created: {datetime.utcnow().isoformat()}\n")
                    f.write(f"# Permissions: {permissions}\n")
                    f.write(f"API_KEY={api_key}\n")
                
                print(f"   Saved to: {key_file}")
            
            conn.commit()
            print(f"✅ Successfully set up security for {node}")
            
        except Exception as e:
            print(f"❌ Error setting up {node}: {e}")
            conn.rollback()
        finally:
            conn.close()

def print_summary():
    """Print summary of created security resources."""
    print("\n" + "="*70)
    print("🔐 FED-MED-FL SECURITY INITIALIZATION COMPLETE")
    print("="*70)
    
    print("\n📋 Default User Accounts:")
    print("┌─────────────────────────────────────┬──────────────┬────────┐")
    print("│ Email                               │ Role         │ Node   │")
    print("├─────────────────────────────────────┼──────────────┼────────┤")
    print("│ admin@node1.fed-med-fl.com          │ admin        │ node1  │")
    print("│ doctor@node1.fed-med-fl.com         │ doctor       │ node1  │")
    print("│ researcher@node1.fed-med-fl.com     │ researcher   │ node1  │")
    print("│ admin@node2.fed-med-fl.com          │ admin        │ node2  │")
    print("│ doctor@node2.fed-med-fl.com         │ doctor       │ node2  │")
    print("│ researcher@node2.fed-med-fl.com     │ researcher   │ node2  │")
    print("│ admin@node3.fed-med-fl.com          │ admin        │ node3  │")
    print("│ doctor@node3.fed-med-fl.com         │ doctor       │ node3  │")
    print("│ researcher@node3.fed-med-fl.com     │ researcher   │ node3  │")
    print("│ viewer@fed-med-fl.com               │ viewer       │ node1  │")
    print("└─────────────────────────────────────┴──────────────┴────────┘")
    
    print("\n🔑 Default Passwords:")
    print("  • Admin passwords: AdminNode{X}@2026")
    print("  • Doctor passwords: DoctorNode{X}@2026") 
    print("  • Researcher passwords: ResearcherNode{X}@2026")
    print("  • Viewer password: ViewerAccess@2026")
    
    print("\n🛡️ Security Features Enabled:")
    print("  ✅ JWT Authentication (30min expiry)")
    print("  ✅ Role-based Access Control (RBAC)")
    print("  ✅ Password strength validation")
    print("  ✅ Account lockout (5 failed attempts)")
    print("  ✅ Rate limiting per role")
    print("  ✅ Audit logging")
    print("  ✅ API key authentication")
    
    print("\n📁 API Keys saved to:")
    print("  • storage/node1_api_key.txt")
    print("  • storage/node2_api_key.txt") 
    print("  • storage/node3_api_key.txt")
    
    print("\n🚀 Next Steps:")
    print("  1. Test login: POST /api/auth/login")
    print("  2. Access protected endpoints with Bearer token")
    
    print("\n⚠️  IMPORTANT SECURITY NOTES:")
    print("  • Change default passwords in production!")
    print("  • Use strong JWT_SECRET_KEY in production!")
    print("  • Enable HTTPS in production!")
    print("  • Regularly rotate API keys!")
    
    print("\n" + "="*70)

def main():
    """Main initialization function."""
    print("🔐 Initializing Fed-Med-FL Security...")
    print("="*50)
    
    try:
        # Create default users
        create_default_users()
        
        # Print summary
        print_summary()
        
    except Exception as e:
        print(f"❌ Security initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()