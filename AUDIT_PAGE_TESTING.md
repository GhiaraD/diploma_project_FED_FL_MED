# Testare Pagină Audit - Ghid Complet

## 🎯 Obiectiv
Să testăm pagina de audit și să vedem ce log-uri sunt înregistrate pentru diferite acțiuni.

---

## 📋 Pași de Testare

### 1. **Testare Inițială - Vezi Log-urile Existente**

#### Pas 1.1: Login
1. Deschide browser la http://localhost:3001/login
2. Introdu credențialele:
   - Email: `admin@node1.fed-med-fl.com`
   - Password: `AdminNode1@2026`
3. Click "Sign In"
4. Ar trebui să fii redirectat la Dashboard

#### Pas 1.2: Accesează Pagina Audit
1. Click pe "Audit" în sidebar (sau navighează la http://localhost:3001/audit)
2. Ar trebui să vezi o pagină cu:
   - Header "Security Audit Logs"
   - Filtre (Search și Event Type)
   - Tabel cu log-uri

#### Pas 1.3: Verifică Log-urile Existente
Ar trebui să vezi log-uri de tipul:
- ✅ `login_success` - Login-urile tale anterioare
- ❌ `login_failed` - Încercări eșuate (dacă ai avut)
- 🚪 `logout` - Logout-uri anterioare

**Ce să observi:**
- Timestamp (când s-a întâmplat)
- Event type (tipul evenimentului)
- User ID (ID-ul tău de utilizator)
- Endpoint (ex: `POST /api/auth/login`)
- IP Address (adresa ta IP)
- Status (200 pentru success, 401 pentru failed)

---

### 2. **Generare Log-uri Noi - Testare Autentificare**

#### Test 2.1: Login Failed
1. Deschide o fereastră incognito/private
2. Navighează la http://localhost:3001/login
3. Introdu credențiale greșite:
   - Email: `admin@node1.fed-med-fl.com`
   - Password: `WrongPassword123`
4. Click "Sign In"
5. Ar trebui să vezi eroare

#### Test 2.2: Verifică Log-ul
1. Revino la fereastra cu sesiunea activă
2. Refresh pagina de audit (F5 sau click pe butonul Refresh)
3. Ar trebui să vezi un nou log:
   - ❌ `login_failed`
   - Timestamp recent
   - Status: 401

#### Test 2.3: Logout și Re-login
1. Click pe avatar (colț dreapta-sus)
2. Click "Logout"
3. Login din nou cu credențiale corecte
4. Navighează la pagina Audit
5. Ar trebui să vezi:
   - 🚪 `logout` (de la logout-ul anterior)
   - ✅ `login_success` (de la login-ul nou)

---

### 3. **Testare Filtre**

#### Test 3.1: Filtrare după Event Type
1. În dropdown-ul "Event Type", selectează:
   - "LOGIN_SUCCESS" - ar trebui să vezi doar login-uri reușite
   - "LOGIN_FAILED" - ar trebui să vezi doar login-uri eșuate
   - "LOGOUT" - ar trebui să vezi doar logout-uri
   - "All Events" - ar trebui să vezi toate

#### Test 3.2: Căutare Text
1. În câmpul "Search", scrie:
   - "login" - ar trebui să vezi toate evenimentele cu "login"
   - "admin" - ar trebui să vezi evenimentele pentru user admin
   - "/api/auth" - ar trebui să vezi toate request-urile către auth API

---

### 4. **Ce Log-uri LIPSESC momentan** ❌

Următoarele acțiuni **NU** sunt încă logate (le vom implementa):

#### 4.1: Dataset Actions
- [ ] Register dataset
- [ ] Activate dataset
- [ ] Delete dataset
- [ ] Browse filesystem

#### 4.2: Model Actions
- [ ] Promote model
- [ ] Train model (local)
- [ ] View model details

#### 4.3: Inference Actions
- [ ] Start inference
- [ ] View inference results
- [ ] Generate Grad-CAM

#### 4.4: Federated Learning
- [ ] Join federated training
- [ ] Complete federated training
- [ ] Upload/download model

#### 4.5: Jobs
- [ ] View job status
- [ ] View job logs

---

## 🔍 Ce să Cauți în Log-uri

### Informații Importante:
1. **Timestamp** - Când s-a întâmplat acțiunea
2. **Event Type** - Ce tip de acțiune (login, logout, etc.)
3. **User ID** - Cine a făcut acțiunea
4. **Endpoint** - Ce API endpoint a fost accesat
5. **IP Address** - De unde a venit request-ul
6. **Status** - Cod HTTP (200 = success, 401 = unauthorized, etc.)
7. **Duration** - Cât a durat request-ul (în ms)

### Exemple de Log-uri:

#### Login Success:
```
Timestamp: 2026-04-26 15:30:45
Event: login_success ✅
User: user_136e5eff9cccd137
Endpoint: POST /api/auth/login
IP: 172.18.0.1
Status: 200
```

#### Login Failed:
```
Timestamp: 2026-04-26 15:28:12
Event: login_failed ❌
User: -
Endpoint: POST /api/auth/login
IP: 172.18.0.1
Status: 401
```

#### Logout:
```
Timestamp: 2026-04-26 15:45:20
Event: logout 🚪
User: user_136e5eff9cccd137
Endpoint: POST /api/auth/logout
IP: 172.18.0.1
Status: 200
```

---

## 🐛 Troubleshooting

### Pagina de audit nu se încarcă
```bash
# Verifică log-urile UI
docker logs diploma_project_fed_fl_med-node1-ui-1 --tail 50

# Verifică log-urile API
docker logs diploma_project_fed_fl_med-node1-api-1 --tail 50
```

### Nu văd log-uri
```bash
# Verifică dacă există log-uri în baza de date
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM audit_logs')
print(f'Total logs: {cursor.fetchone()[0]}')
cursor.execute('SELECT event_type, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 5')
print('Recent logs:')
for row in cursor.fetchall():
    print(f'  {row[0]} - {row[1]}')
conn.close()
"
```

### Eroare 403 Forbidden
- Doar utilizatorii cu rol "admin" pot vedea audit logs
- Verifică că ești logat ca admin

### Filtrele nu funcționează
- Refresh pagina (F5)
- Verifică că ai log-uri de tipul pe care îl cauți

---

## 📊 Statistici Curente

Verifică câte log-uri ai:
```bash
docker exec diploma_project_fed_fl_med-node1-api-1 python -c "
import sqlite3
conn = sqlite3.connect('/storage/node.db')
cursor = conn.cursor()
cursor.execute('SELECT event_type, COUNT(*) as count FROM audit_logs GROUP BY event_type')
print('Log statistics:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
"
```

---

## 🚀 Next Steps

După ce testezi pagina de audit cu log-urile actuale:

1. **Implementăm logging pentru datasets**
   - Register, activate, delete

2. **Implementăm logging pentru models**
   - Promote, train

3. **Implementăm logging pentru inference**
   - Start, complete

4. **Implementăm logging pentru federated learning**
   - Join, complete

5. **Testăm din nou** pentru a vedea toate tipurile de log-uri

---

## ✅ Checklist de Testare

- [ ] Login cu credențiale corecte → Vezi `login_success`
- [ ] Login cu credențiale greșite → Vezi `login_failed`
- [ ] Logout → Vezi `logout`
- [ ] Filtrare după event type funcționează
- [ ] Căutare text funcționează
- [ ] Refresh button funcționează
- [ ] Tabelul arată frumos (Material-UI)
- [ ] Timestamp-urile sunt corecte
- [ ] User ID-urile sunt afișate
- [ ] Status codes sunt colorate corect

---

**Gata de testare! 🎉**

Deschide http://localhost:3001/login și începe testarea!
