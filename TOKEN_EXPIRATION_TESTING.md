# Token Expiration Management - Testing Guide

## Overview
Implementarea gestionării expirării token-urilor JWT cu relogare forțată și notificări pentru utilizator.

## Features Implemented

### 1. Backend Token Configuration
- **Current Setting**: 3 minutes (pentru testare)
- **Production Setting**: Va fi schimbat la 24 ore după testare
- **Location**: `services/node/api/app/security.py`
- **Variable**: `ACCESS_TOKEN_EXPIRE_MINUTES = 3`

### 2. Frontend Token Management
- **Automatic Token Validation**: Verifică token-ul la fiecare 30 secunde
- **JWT Decoding**: Decodează token-ul pentru a obține timpul de expirare
- **Automatic Logout**: Forțează logout-ul când token-ul expiră
- **Redirect to Login**: Redirecționează automat la pagina de login

### 3. API Request Interceptor
- **Automatic 401 Handling**: Interceptează răspunsurile 401 Unauthorized
- **Token Validation**: Verifică token-ul înainte de fiecare request
- **Automatic Logout**: Forțează logout-ul la primirea unui 401

### 4. User Notifications
- **Expiration Warning**: Afișează avertizare cu 60 secunde înainte de expirare
- **Countdown Timer**: Arată timpul rămas până la expirare
- **Action Buttons**: Opțiuni pentru re-login sau logout imediat

## Testing Steps

### Step 1: Login and Monitor
1. Accesează http://localhost:3001
2. Loghează-te cu credențialele admin
3. Observă că token-ul este valid pentru 3 minute

### Step 2: Token Expiration Warning
1. Așteaptă 2 minute după login
2. În ultimele 60 secunde, ar trebui să apară o notificare de avertizare
3. Notificarea arată timpul rămas și opțiuni pentru acțiune

### Step 3: Automatic Logout
1. Dacă nu iei nicio acțiune, după 3 minute token-ul expiră
2. Sistemul ar trebui să te delogheze automat
3. Ești redirecționat la pagina de login

### Step 4: API Request Handling
1. Dacă faci un request API după expirarea token-ului
2. Sistemul ar trebui să detecteze 401 și să te delogheze automat

## Files Modified

### Backend Files
- `services/node/api/app/security.py` - Token expiration time
- `services/node/api/app/audit_helper.py` - Enhanced audit logging
- `services/node/api/app/main.py` - Enhanced audit logging with timing

### Frontend Files
- `services/node/ui/src/contexts/AuthContext.tsx` - Token expiration management
- `services/node/ui/src/hooks/useApiInterceptor.ts` - API request interceptor
- `services/node/ui/src/components/TokenExpirationWarning.tsx` - User notifications
- `services/node/ui/src/components/Layout.tsx` - Integration of expiration handling

## Configuration Changes

### For Testing (Current)
```javascript
ACCESS_TOKEN_EXPIRE_MINUTES = 3  // 3 minutes
```

### For Production (After Testing)
```javascript
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  // 24 hours (24 * 60 minutes)
```

## Expected Behavior

1. **Login**: Token valid pentru 3 minute
2. **2 minutes**: Funcționare normală
3. **2:00-3:00**: Avertizare de expirare cu countdown
4. **3:00+**: Logout automat și redirect la login
5. **API Calls**: Interceptate și gestionate automat

## Security Benefits

1. **Automatic Session Management**: Nu mai sunt sesiuni "uitate" active
2. **User Awareness**: Utilizatorii sunt avertizați despre expirare
3. **Graceful Handling**: Logout-ul este gestionat elegant, nu brutal
4. **Enhanced Audit**: Toate acțiunile sunt înregistrate cu timing precis

## Next Steps After Testing

1. Verifică că toate funcționalitățile merg corect
2. Schimbă `ACCESS_TOKEN_EXPIRE_MINUTES` la 1440 (24 ore)
3. Testează audit logging-ul îmbunătățit
4. Verifică că duration și status sunt populate în audit logs