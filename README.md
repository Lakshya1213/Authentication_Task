# Google OAuth Authentication POC (FastAPI)

POC 1 focuses **only** on Google OAuth login, token storage, connected account management, and audit logging. No Calendar, Gmail, Slack, or other integrations.

---

## Quick start

### Prerequisites

- Python 3.11+
- PostgreSQL running locally
- Google Cloud OAuth 2.0 Client (Web application)

### 1. Google Cloud setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. **APIs & Services → OAuth consent screen** — configure for testing (add your email as test user)
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URIs (register **both** for local dev):
     - `http://127.0.0.1:8000/auth/google/callback`
     - `http://localhost:8000/auth/google/callback`
5. Copy **Client ID** and **Client Secret**

### 2. Database setup

```sql
CREATE DATABASE oauth_poc;
```

### 3. Environment variables

```bash
cd app
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
DATABASE_URL=postgresql://postgres:password@localhost:5432/oauth_poc
SECRET_KEY=<random-64-char-hex>
FERNET_KEY=<fernet-key>
```

Generate keys:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Install and run

```bash
cd app
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

Open API docs: http://localhost:8000/docs

### 5. Test the flow

1. Open http://127.0.0.1:8000 in your browser (use this **or** `localhost` — not both)
2. Click **Continue with Google** and approve permissions
3. You are redirected to the dashboard with your profile and connected apps
4. Use **Disconnect Google** to remove stored tokens

API docs remain available at http://localhost:8000/docs

> **Important:** `127.0.0.1` and `localhost` are different cookie domains. If login fails with "Invalid OAuth state parameter", register both redirect URIs in Google Console and always use the same URL you started with.

---

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/google/login` | No | Redirect to Google consent screen |
| GET | `/auth/google/callback` | No | OAuth callback — exchange code, store tokens |
| GET | `/connected-apps` | Session | List connected providers |
| POST | `/disconnect/google` | Session | Disconnect Google, delete tokens |
| GET | `/me` | Session | Current user profile (POC helper) |
| GET | `/health` | No | Health check |

---

## Project structure

```
app/
├── main.py                 # App entry, middleware, logging, static files
├── static/                 # Frontend (HTML, CSS, JS)
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── config.py               # Environment settings
├── db/database.py          # SQLAlchemy engine & sessions
├── models/                 # Database tables (ORM)
├── routes/auth.py          # HTTP endpoints
├── services/google_auth.py # OAuth business logic
├── schemas/auth_schema.py  # Request/response shapes
├── utils/encryption.py     # Fernet token encryption
├── requirements.txt
├── .env.example
└── README.md
```

---

## Learning guide

The sections below explain **why** each piece exists, how they connect, and core OAuth concepts for first-time learners.

---

# File-by-file explanation

## `main.py`

**Why it exists:** Single entry point that bootstraps the FastAPI application.

**Problem it solves:** Without a central entry, routes, middleware, and startup logic would be scattered.

**Interactions:**
- Loads `config.py` for settings
- Calls `init_db()` from `database.py` on startup
- Registers `routes/auth.py` router
- Adds `SessionMiddleware` (signed cookie sessions using `SECRET_KEY`)

**Request flow:**
1. HTTP request hits Uvicorn → FastAPI `app`
2. Session middleware reads/writes session cookie
3. Router dispatches to handler in `auth.py`
4. Unhandled errors become structured JSON via exception handlers

**Design choice:** Thin `main.py` — no business logic here. Keeps the app composable and testable.

---

## `config.py`

**Why it exists:** Central, typed configuration from environment variables.

**Problem it solves:** Hard-coded secrets and scattered `os.getenv()` calls are error-prone and insecure.

**Interactions:** Used by `database.py`, `encryption.py`, `google_auth.py`, and `main.py`.

**Design choice:** `pydantic-settings` validates required vars at startup — fail fast if `.env` is incomplete.

---

## `db/database.py`

**Why it exists:** Manages PostgreSQL connection and request-scoped sessions.

**Problem it solves:** Each route needs a DB session that opens and closes correctly.

**Interactions:**
- `get_db()` injected into routes via FastAPI `Depends`
- `init_db()` creates tables from models in `models/`
- All models inherit from `Base`

**Request flow:** Route runs → `get_db()` yields session → route commits/reads → session closed in `finally`.

**Design choice:** Sync SQLAlchemy is sufficient for this POC; keeps learning curve lower than async SQLAlchemy.

---

## `models/user.py`

**Why:** Stores identity from Google (name, email, picture).

**Problem:** OAuth gives profile data once per login; we persist it for `/connected-apps`, audit logs, and future features.

**Relationships:** One user → many `connected_accounts`, many `audit_logs`.

---

## `models/connected_account.py`

**Why:** Separates *identity* (user) from *integration* (Google connection).

**Problem:** A user might connect Google today, disconnect tomorrow, or connect other providers in POC 2+. This table tracks provider, status, and scopes without overloading `users`.

**Relationships:** Many-to-one with `users`; one-to-one with `oauth_tokens`.

---

## `models/oauth_token.py`

**Why:** Stores encrypted OAuth credentials separately from account metadata.

**Problem:** Tokens are highly sensitive and rotate independently of profile data. Isolating them limits exposure and supports encryption at the column level.

**Security:** Only Fernet-encrypted strings are stored — never plaintext.

---

## `models/audit_log.py`

**Why:** Compliance and debugging — who did what, when, and whether it succeeded.

**Problem:** OAuth failures are hard to diagnose without a trail. Enterprise systems require immutable audit records.

**Actions logged:** `login`, `connect`, `disconnect`, `token_refresh`, `failure`.

---

## `routes/auth.py`

**Why:** HTTP layer — maps URLs to service calls.

**Problem:** Keeps transport concerns (status codes, redirects, sessions) separate from OAuth logic.

**Interactions:** Calls `GoogleAuthService`, uses `get_db()`, validates session for protected routes.

**Design choice:** Routes stay thin (~10–20 lines per handler). All Google/DB work lives in `services/google_auth.py`.

---

## `services/google_auth.py`

**Why:** Reusable business logic for OAuth — the “brain” of the POC.

**Problem:** OAuth involves many steps (authorize URL, token exchange, profile fetch, encrypt, persist, audit). Putting this in routes would be unmaintainable.

**Key methods:**
- `build_authorization_url()` — consent screen redirect
- `handle_oauth_callback()` — full post-login pipeline
- `disconnect_google()` — revoke local connection
- `refresh_access_token()` — refresh flow + audit (for future API calls)

**Design choice:** Service class + dependency injection makes unit testing and POC 2 extensions straightforward.

---

## `schemas/auth_schema.py`

**Why:** Pydantic models define API response shapes and error format.

**Problem:** Without schemas, responses are inconsistent dicts; OpenAPI docs are poor.

**Design choice:** Never include tokens in schemas — only safe fields like `provider` and `status`.

---

## `utils/encryption.py`

**Why:** Encrypt/decrypt OAuth tokens with Fernet before DB write/read.

**Problem:** Database backups or SQL injection must not leak usable Google tokens.

**Functions:** `encrypt_token()`, `decrypt_token()`.

---

# Complete OAuth flow (step by step)

```
User clicks "Login with Google"
        ↓
GET /auth/google/login
        ↓
Google Consent Screen
        ↓
Google returns authorization code
        ↓
GET /auth/google/callback?code=...&state=...
        ↓
Token exchange
        ↓
Fetch user profile
        ↓
Create/update user
        ↓
Create/update connected account
        ↓
Encrypt tokens
        ↓
Store tokens
        ↓
Create audit logs
        ↓
Return success JSON + session cookie
```

### Step 1: User clicks Login

| | |
|---|---|
| **Input** | Browser navigates to `/auth/google/login` |
| **Processing** | Generate random `state`, store in session, build Google authorize URL with `client_id`, `redirect_uri`, `scope`, `response_type=code` |
| **Output** | HTTP 302 redirect to `accounts.google.com` |
| **Database** | None |
| **Security** | `state` prevents CSRF on callback |

### Step 2: Google consent screen

| | |
|---|---|
| **Input** | User credentials + permission approval |
| **Processing** | Google validates client and redirect URI |
| **Output** | Redirect to `http://localhost:8000/auth/google/callback?code=AUTH_CODE&state=...` |
| **Database** | None |
| **Security** | User explicitly grants scopes; consent screen shows what app receives |

### Step 3: Callback receives code

| | |
|---|---|
| **Input** | Query params: `code`, `state` (or `error`) |
| **Processing** | Validate `state` matches session; reject missing `code` |
| **Output** | Proceed to token exchange or 400 JSON error |
| **Database** | None yet |
| **Security** | State mismatch → reject (CSRF) |

### Step 4: Token exchange

| | |
|---|---|
| **Input** | Authorization `code`, `client_id`, `client_secret`, `redirect_uri` |
| **Processing** | POST to `https://oauth2.googleapis.com/token` (Authlib) |
| **Output** | `access_token`, optional `refresh_token`, `expires_in` |
| **Database** | None yet |
| **Security** | Code is single-use and short-lived; secret never sent to browser |

### Step 5: Fetch profile

| | |
|---|---|
| **Input** | `access_token` in Authorization header |
| **Processing** | GET Google userinfo endpoint |
| **Output** | `name`, `email`, `picture`, `sub` |
| **Database** | None yet |
| **Security** | Access token used server-side only |

### Step 6: Create/update user

| | |
|---|---|
| **Input** | Profile JSON |
| **Processing** | Upsert by unique `email` |
| **Output** | `User` row |
| **Database** | `INSERT` or `UPDATE users` |
| **Security** | Email from Google is trusted identity for this POC |

### Step 7: Connected account + encrypted tokens

| | |
|---|---|
| **Input** | Token response + user id |
| **Processing** | Upsert `connected_accounts`; Fernet-encrypt tokens; upsert `oauth_tokens` |
| **Output** | Linked account with status `connected` |
| **Database** | `INSERT/UPDATE connected_accounts`, `oauth_tokens` |
| **Security** | Plaintext tokens exist only in memory during request |

### Step 8: Audit logs

| | |
|---|---|
| **Input** | user id, action, status |
| **Processing** | Insert audit rows for `login` and `connect` |
| **Output** | Audit trail |
| **Database** | `INSERT audit_logs` |
| **Security** | Supports forensics without storing secrets |

### Step 9: Success response

| | |
|---|---|
| **Input** | Committed user record |
| **Processing** | Set `user_id` in session cookie |
| **Output** | JSON `{ status, message, user }` — **no tokens** |
| **Database** | Transaction committed |
| **Security** | HttpOnly session cookie for subsequent API calls |

---

# FastAPI architecture (why each folder exists)

| Layer | Folder / file | Responsibility |
|-------|---------------|----------------|
| **Routes** | `routes/` | HTTP: URLs, status codes, redirects, auth checks |
| **Services** | `services/` | Business rules, OAuth, orchestration |
| **Models** | `models/` | Database tables and relationships |
| **Schemas** | `schemas/` | API contracts (Pydantic) |
| **Utils** | `utils/` | Cross-cutting helpers (encryption) |
| **Config** | `config.py` | Environment and constants |
| **Database** | `db/database.py` | Engine, sessions, table creation |

**Analogy:** Restaurant — routes are waiters, services are chefs, models are the pantry inventory schema, schemas are the menu descriptions, config is the supplier list, database.py is the kitchen door policy.

---

# OAuth concepts (beginner-friendly)

### OAuth

A standard that lets users grant your app limited access to their Google account **without giving you their Google password**.

*Example:* “Sign in with Google” — you get a token, not their password.

### Authorization Code Flow

The most secure flow for server-side apps:

1. Browser gets a **code** (not tokens)
2. **Server** exchanges code for tokens using **client secret**

The secret never reaches the browser.

### Consent Screen

Google UI listing requested permissions. User must click Allow.

### Redirect URI

Exact URL Google sends the user back to. Must match Google Console registration exactly (`http://localhost:8000/auth/google/callback`).

### Access Token

Short-lived key to call Google APIs (e.g. userinfo). Like a day pass.

### Refresh Token

Long-lived key to obtain new access tokens without re-login. Like a membership card you use to get new day passes.

### OAuth Scopes

Permissions requested. This POC uses `openid email profile` only — basic identity, no Gmail/Calendar.

### Token Expiry

Access tokens expire (often ~1 hour). `expires_at` is stored so POC 2 can refresh before API calls.

---

# Database design

```
users (1) ──< connected_accounts (1) ── oauth_tokens
  │
  └──< audit_logs
```

| Table | Purpose |
|-------|---------|
| **users** | Canonical person — email, name, avatar |
| **connected_accounts** | Which provider is linked and whether it's active |
| **oauth_tokens** | Encrypted secrets for API access |
| **audit_logs** | Security/compliance event history |

**Why split users and connected_accounts?** Identity persists if user disconnects Google. **Why separate oauth_tokens?** Different security classification and rotation lifecycle.

---

# Security

### Why encrypt tokens?

DB breach + plaintext tokens = attacker accesses user Google data. Fernet encryption means attackers also need `FERNET_KEY` from secrets management.

### Why `.env`?

Keeps secrets out of source control. `.env.example` documents keys without values.

### Why refresh tokens matter?

Access tokens expire quickly. Refresh tokens allow silent renewal for background jobs (POC 2+) without repeated consent.

### Common OAuth mistakes

- Exposing `client_secret` in frontend code
- Storing plaintext tokens
- Skipping `state` CSRF validation
- Wrong redirect URI
- Logging tokens
- Returning tokens in API responses

### Enterprise practices

- Secrets in vaults (AWS Secrets Manager, HashiCorp Vault)
- Token encryption with KMS-managed keys
- Key rotation
- Least-privilege scopes
- Audit logging and alerting
- Short session TTL + refresh token rotation

---

# API walkthrough

## GET `/auth/google/login`

**Request:** Browser navigation — no body.

**Response:** `302` redirect to Google.

**Processing:** Create state → session → build authorize URL.

**Errors:** Misconfiguration → 500 at startup if env invalid.

---

## GET `/auth/google/callback`

**Request example:**

```
GET /auth/google/callback?code=4/0A...&state=abc123
Cookie: oauth_poc_session=...
```

**Success response:**

```json
{
  "status": "success",
  "message": "Successfully authenticated with Google",
  "user": {
    "id": 1,
    "name": "Jane Doe",
    "email": "jane@gmail.com",
    "picture": "https://lh3.googleusercontent.com/..."
  }
}
```

**Error response:**

```json
{
  "status": "failed",
  "error_type": "oauth_error",
  "message": "Missing authorization code"
}
```

**DB ops:** Upsert user, connected_account, oauth_token; insert audit_logs.

**Error scenarios:** Missing code, state mismatch, token exchange failure, encryption failure, DB failure.

---

## GET `/connected-apps`

**Request:** Session cookie required.

**Success:**

```json
[
  {
    "provider": "google",
    "status": "connected",
    "scopes": "openid email profile",
    "connected_at": "2026-06-25T10:00:00Z"
  }
]
```

**401 if not logged in.**

**DB:** `SELECT connected_accounts WHERE user_id = ?`

---

## POST `/disconnect/google`

**Request:** Session cookie, empty body.

**Success:**

```json
{
  "status": "success",
  "message": "Google account disconnected successfully",
  "provider": "google"
}
```

**DB:** Update status to `disconnected`, delete oauth_tokens row, insert audit_log.

**Errors:** 404 if no Google connection; 401 if no session.

---

## License

MIT — educational POC.
