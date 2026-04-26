# Fed-Med-FL Security - Quick Reference Card

## 🔐 Login Credentials

### Node 1
- **URL**: http://localhost:3001
- **Email**: admin@node1.fed-med-fl.com
- **Password**: AdminNode1@2026

### Node 2
- **URL**: http://localhost:3002
- **Email**: admin@node2.fed-med-fl.com
- **Password**: AdminNode2@2026

### Node 3
- **URL**: http://localhost:3003
- **Email**: admin@node3.fed-med-fl.com
- **Password**: AdminNode3@2026

---

## 🧪 API Testing Commands

### Login (Get JWT Token)
```bash
# Node 1
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@node1.fed-med-fl.com&password=AdminNode1@2026"

# Node 2
curl -X POST http://localhost:8002/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@node2.fed-med-fl.com&password=AdminNode2@2026"

# Node 3
curl -X POST http://localhost:8003/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@node3.fed-med-fl.com&password=AdminNode3@2026"
```

### Access Protected Endpoint
```bash
# Get token first, then:
TOKEN="your_jwt_token_here"

# Test node status
curl http://localhost:8001/api/node/status \
  -H "Authorization: Bearer $TOKEN"

# Test datasets
curl http://localhost:8001/api/data/list \
  -H "Authorization: Bearer $TOKEN"

# Test models
curl http://localhost:8001/api/models/registry \
  -H "Authorization: Bearer $TOKEN"
```

### Logout
```bash
curl -X POST http://localhost:8001/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🌐 Browser Testing Checklist

### Login Flow
- [ ] Navigate to http://localhost:3001
- [ ] Should redirect to /login
- [ ] Enter: admin@node1.fed-med-fl.com / AdminNode1@2026
- [ ] Click "Sign In"
- [ ] Should redirect to dashboard
- [ ] User menu should show in top-right

### Navigation
- [ ] Click Dashboard → Should load
- [ ] Click Datasets → Should load
- [ ] Click Federated → Should load
- [ ] Click Models → Should load
- [ ] Click Inference → Should load
- [ ] Click Jobs → Should load
- [ ] Click Audit → Should show security logs

### User Menu
- [ ] Click avatar in top-right
- [ ] Should show email and role
- [ ] Click Logout
- [ ] Should redirect to /login
- [ ] Try accessing /datasets → Should redirect to /login

### Repeat for Node 2 and Node 3
- [ ] http://localhost:3002 with admin@node2.fed-med-fl.com
- [ ] http://localhost:3003 with admin@node3.fed-med-fl.com

---

## 🔧 Troubleshooting

### Can't Login
```bash
# Check if API is running
docker ps | grep api

# Check API logs
docker logs diploma_project_fed_fl_med-node1-api-1

# Test login via curl
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@node1.fed-med-fl.com&password=AdminNode1@2026"
```

### UI Not Loading
```bash
# Check if UI is running
docker ps | grep ui

# Check UI logs
docker logs diploma_project_fed_fl_med-node1-ui-1

# Rebuild UI
docker compose build node1-ui
docker compose restart node1-ui
```

### 403 Forbidden Errors
```bash
# Check if token is valid
# Token expires after 30 minutes
# Login again to get new token
```

### Database Issues
```bash
# Check if user exists
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT email, role FROM users')
print(cursor.fetchall())
conn.close()
"
```

---

## 📝 Common Tasks

### Create New User
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3, bcrypt, uuid
from datetime import datetime

conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()

user_id = str(uuid.uuid4())
email = 'newuser@node1.fed-med-fl.com'
password = 'SecurePassword@2026'
role = 'doctor'  # or 'researcher', 'viewer'
node_id = 'node1'

password_bytes = password.encode('utf-8')[:72]
password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
now = datetime.utcnow().isoformat()

cursor.execute('''
    INSERT INTO users (id, email, password_hash, role, node_id, is_active, created_at, failed_login_attempts, password_changed_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (user_id, email, password_hash, role, node_id, 1, now, 0, now))

conn.commit()
print(f'Created user: {email}')
conn.close()
"
```

### View Audit Logs
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT event_type, user_email, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 10')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```

### Reset Password
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3, bcrypt
from datetime import datetime

conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()

email = 'admin@node1.fed-med-fl.com'
new_password = 'NewPassword@2026'

password_bytes = new_password.encode('utf-8')[:72]
password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
now = datetime.utcnow().isoformat()

cursor.execute('''
    UPDATE users 
    SET password_hash = ?, password_changed_at = ?, failed_login_attempts = 0, locked_until = NULL
    WHERE email = ?
''', (password_hash, now, email))

conn.commit()
print(f'Password reset for: {email}')
conn.close()
"
```

---

## 🚨 Emergency Commands

### Unlock Account
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE email = ?', ('admin@node1.fed-med-fl.com',))
conn.commit()
print('Account unlocked')
conn.close()
"
```

### View All Users
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT email, role, node_id, is_active FROM users')
for row in cursor.fetchall():
    print(f'{row[0]:40} {row[1]:15} {row[2]:10} Active: {bool(row[3])}')
conn.close()
"
```

### Restart All Services
```bash
docker compose restart node1-api node1-ui node2-api node2-ui node3-api node3-ui
```

---

## 📊 Status Check

### Quick Health Check
```bash
# Check all containers
docker compose ps

# Check API health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Check UI access
curl -I http://localhost:3001
curl -I http://localhost:3002
curl -I http://localhost:3003
```

---

## 🔑 Security Configuration

### JWT Settings
- **Algorithm**: HS256
- **Token Expiry**: 30 minutes
- **Secret Key**: `fed-med-fl-secret-key-2026-change-in-production` (CHANGE IN PRODUCTION!)

### Rate Limits
- **Admin**: 1000 requests/minute
- **Doctor**: 100 requests/minute
- **Researcher**: 50 requests/minute
- **Viewer**: 30 requests/minute

### Account Lockout
- **Failed Attempts**: 5
- **Lockout Duration**: 15 minutes
- **Auto Unlock**: Yes

---

## 📞 Support

### Logs Location
- **API Logs**: `docker logs diploma_project_fed_fl_med-node1-api-1`
- **UI Logs**: `docker logs diploma_project_fed_fl_med-node1-ui-1`
- **Database**: `/storage/node.db` (inside container)
- **Audit Logs**: `audit_logs` table in database

### Documentation
- `SECURITY_ARCHITECTURE.md` - Security design
- `SECURITY_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `UI_SECURITY_COMPLETE.md` - UI implementation
- `SECURITY_IMPLEMENTATION_FINAL.md` - Complete summary

---

*Last Updated: April 26, 2026*
