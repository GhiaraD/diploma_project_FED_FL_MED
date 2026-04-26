#!/usr/bin/env python3
"""
Initialize security for Fed-Med-FL platform.

Creates database tables and default users for each node.
"""
import sys
import os
from pathlib import Path

# Add the node API to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "node" / "api"))

from app.database import engine, Base, SessionLocal, User, ApiKey
from app.security import security_manager
from datetime import datetime, timedelta
import hashlib
import secrets
import json


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def create_default_users():
    """Create default users for each node."""
    db = SessionLocal()
    
    try:
        # Default users for each node
        default_users = [
            # Node 1 users
            {
                "email": "admin@node1.fed-med-fl.com",
                "password": "AdminNode1@2026",
                "role": "admin",
                "node_id": "node1"
            },
            {
                "email": "doctor@node1.fed-med-fl.com", 
                "password": "DoctorNode1@2026",
                "role": "doctor",
                "node_id": "node1"
            },
            {
                "email": "researcher@node1.fed-med-fl.com",
                "password": "ResearcherNode1@2026", 
                "role": "researcher",
                "node_id": "node1"
            },
            
            # Node 2 users
            {
                "email": "admin@node2.fed-med-fl.com",
                "password": "AdminNode2@2026",
                "role": "admin", 
                "node_id": "node2"
            },
            {
                "email": "doctor@node2.fed-med-fl.com",
                "password": "DoctorNode2@2026",
                "role": "doctor",
                "node_id": "node2"
            },
            {
                "email": "researcher@node2.fed-med-fl.com",
                "password": "ResearcherNode2@2026",
                "role": "researcher", 
                "node_id": "node2"
            },
            
            # Node 3 users
            {
                "email": "admin@node3.fed-med-fl.com",
                "password": "AdminNode3@2026",
                "role": "admin",
                "node_id": "node3"
            },
            {
                "email": "doctor@node3.fed-med-fl.com",
                "password": "DoctorNode3@2026", 
                "role": "doctor",
                "node_id": "node3"
            },
            {
                "email": "researcher@node3.fed-med-fl.com",
                "password": "ResearcherNode3@2026",
                "role": "researcher",
                "node_id": "node3"
            },
            
            # Viewer user (can access all nodes)
            {
                "email": "viewer@fed-med-fl.com",
                "password": "ViewerAccess@2026",
                "role": "viewer", 
                "node_id": "node1"  # Default to node1, but can view others
            }
        ]
        
        print("Creating default users...")
        
        for user_data in default_users:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data["email"]).first()
            
            if existing_user:
                print(f"⚠️  User {user_data['email']} already exists, skipping...")
                continue
            
            # Validate password strength
            is_valid, error_msg = security_manager.validate_password_strength(user_data["password"])
            if not is_valid:
                print(f"❌ Password for {user_data['email']} is not strong enough: {error_msg}")
                continue
            
            # Create user
            hashed_password = security_manager.get_password_hash(user_data["password"])
            
            user = User(
                email=user_data["email"],
                password_hash=hashed_password,
                role=user_data["role"],
                node_id=user_data["node_id"],
                is_active=True,
                created_at=datetime.utcnow(),
                password_changed_at=datetime.utcnow()
            )
            
            db.add(user)
            print(f"✅ Created user: {user_data['email']} ({user_data['role']} @ {user_data['node_id']})")
        
        db.commit()
        print(f"✅ Successfully created {len(default_users)} default users")
        
    except Exception as e:
        print(f"❌ Error creating users: {e}")
        db.rollback()
    finally:
        db.close()


def create_api_keys():
    """Create API keys for inter-node communication."""
    db = SessionLocal()
    
    try:
        # API keys for each node to communicate with central and other nodes
        api_keys_data = [
            {
                "node_id": "node1",
                "permissions": ["federated:participate", "central:register", "inter_node:communicate"],
                "description": "Node1 inter-node communication"
            },
            {
                "node_id": "node2", 
                "permissions": ["federated:participate", "central:register", "inter_node:communicate"],
                "description": "Node2 inter-node communication"
            },
            {
                "node_id": "node3",
                "permissions": ["federated:participate", "central:register", "inter_node:communicate"], 
                "description": "Node3 inter-node communication"
            },
            {
                "node_id": "central",
                "permissions": ["*"],  # Central has full permissions
                "description": "Central server master key"
            }
        ]
        
        print("Creating API keys for inter-node communication...")
        
        for key_data in api_keys_data:
            # Check if API key for this node already exists
            existing_key = db.query(ApiKey).filter(ApiKey.node_id == key_data["node_id"]).first()
            
            if existing_key:
                print(f"⚠️  API key for {key_data['node_id']} already exists, skipping...")
                continue
            
            # Generate secure API key
            api_key = f"fed_med_fl_{key_data['node_id']}_{secrets.token_urlsafe(32)}"
            
            # Hash the key for storage
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Create API key record
            api_key_record = ApiKey(
                key_hash=key_hash,
                node_id=key_data["node_id"],
                permissions=json.dumps(key_data["permissions"]),
                expires_at=datetime.utcnow() + timedelta(days=3650),  # 10 years
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            db.add(api_key_record)
            
            print(f"✅ Created API key for {key_data['node_id']}")
            print(f"   Key: {api_key}")
            print(f"   Permissions: {key_data['permissions']}")
            
            # Save key to file for easy access
            key_file = Path(__file__).parent.parent / "storage" / f"{key_data['node_id']}_api_key.txt"
            key_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(key_file, 'w') as f:
                f.write(f"# API Key for {key_data['node_id']}\n")
                f.write(f"# Created: {datetime.utcnow().isoformat()}\n")
                f.write(f"# Permissions: {key_data['permissions']}\n")
                f.write(f"API_KEY={api_key}\n")
            
            print(f"   Saved to: {key_file}")
        
        db.commit()
        print(f"✅ Successfully created API keys")
        
    except Exception as e:
        print(f"❌ Error creating API keys: {e}")
        db.rollback()
    finally:
        db.close()


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
    print("  • storage/central_api_key.txt")
    
    print("\n🚀 Next Steps:")
    print("  1. Update docker-compose.yml with JWT_SECRET_KEY")
    print("  2. Restart services: docker compose up -d")
    print("  3. Test login: POST /api/auth/login")
    print("  4. Access protected endpoints with Bearer token")
    
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
        # Create database tables
        create_tables()
        
        # Create default users
        create_default_users()
        
        # Create API keys
        create_api_keys()
        
        # Print summary
        print_summary()
        
    except Exception as e:
        print(f"❌ Security initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()