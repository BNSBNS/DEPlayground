# Auth Methods Lab

Learn authentication by building it from scratch. No frameworks hiding the magic — just plain TypeScript, HTML, and a single Express server. Each auth method is an isolated vertical slice: click a button, see the full flow, inspect every redirect, token, and header.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────────────────────────────────────┐           │
│  │         Express Server :3000             │           │
│  │                                          │           │
│  │  /                  Landing page         │           │
│  │  /auth/session/*    Username & password  │           │
│  │  /auth/jwt/*        JWT tokens           │           │
│  │  /auth/apikey/*     API key auth         │           │
│  │  /auth/magic/*      Magic link email     │           │
│  │  /auth/oidc/*       OAuth 2.0 / OIDC     │           │
│  │  /auth/entra/*      Entra ID (simulated) │           │
│  │  /auth/saml/*       SAML 2.0             │           │
│  │  /auth/mtls/*       Mutual TLS           │           │
│  └──────────┬───────────────────────────────┘           │
│             │                                            │
│  ┌──────────▼───────────────────────────────┐           │
│  │         Keycloak :8080                   │           │
│  │  realm: oidc   → mimics Google/GitHub    │           │
│  │  realm: entra  → mimics Azure AD         │           │
│  │  realm: saml   → SAML 2.0 IdP           │           │
│  └──────────────────────────────────────────┘           │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Postgres │  │  Redis   │  │ Mailpit  │              │
│  │ :5432    │  │ :6379    │  │ :8025    │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

**One server. One codebase. Eight isolated auth flows.** No React, no Next.js, no Auth.js. You see every HTTP request, every redirect, every token.

## Project Structure

```
auth-methods-lab/
├── docker-compose.yml
├── Dockerfile
├── package.json
├── tsconfig.json
├── keycloak/
│   └── realm-exports/
│       ├── oidc-realm.json
│       ├── entra-realm.json
│       └── saml-realm.json
├── shared/
│   ├── keys/                     # RSA keypair for RS256 (generated at setup)
│   └── certs/                    # Self-signed CA + certs for mTLS (generated at setup)
├── src/
│   ├── server.ts                 # Express app entry point, mounts all route groups
│   ├── db.ts                     # SQLite via better-sqlite3 (users, tokens, api keys)
│   ├── redis.ts                  # Redis client (sessions, token blacklist, rate limits)
│   │
│   ├── auth/
│   │   ├── session/
│   │   │   ├── routes.ts         # POST /login, POST /logout, GET /profile
│   │   │   ├── handlers.ts       # bcrypt verify, session create/destroy
│   │   │   └── NOTES.md          # Flow diagram + security notes
│   │   │
│   │   ├── jwt/
│   │   │   ├── routes.ts         # POST /login, POST /refresh, GET /protected
│   │   │   ├── handlers.ts       # Sign (HS256 + RS256), verify, refresh rotation
│   │   │   └── NOTES.md
│   │   │
│   │   ├── apikey/
│   │   │   ├── routes.ts         # POST /generate, GET /protected
│   │   │   ├── handlers.ts       # Key generation, SHA-256 hashing, lookup, rate limit
│   │   │   └── NOTES.md
│   │   │
│   │   ├── magic/
│   │   │   ├── routes.ts         # POST /send, GET /verify
│   │   │   ├── handlers.ts       # Token generation, email send via SMTP, single-use check
│   │   │   └── NOTES.md
│   │   │
│   │   ├── oidc/
│   │   │   ├── routes.ts         # GET /login, GET /callback, GET /profile
│   │   │   ├── handlers.ts       # Build /authorize URL, PKCE, exchange code, verify ID token
│   │   │   └── NOTES.md
│   │   │
│   │   ├── entra/
│   │   │   ├── routes.ts         # GET /login, GET /callback, GET /profile
│   │   │   ├── handlers.ts       # Same OIDC flow, but parse group/role claims
│   │   │   └── NOTES.md
│   │   │
│   │   ├── saml/
│   │   │   ├── routes.ts         # GET /login, POST /acs (Assertion Consumer Service)
│   │   │   ├── handlers.ts       # Build AuthnRequest, validate assertion XML signature
│   │   │   └── NOTES.md
│   │   │
│   │   └── mtls/
│   │       ├── routes.ts         # GET /protected (separate HTTPS server)
│   │       ├── handlers.ts       # Verify client cert against CA
│   │       └── NOTES.md
│   │
│   ├── middleware/
│   │   ├── debug-panel.ts        # Injects debug panel into HTML responses (shows headers, cookies, tokens)
│   │   └── request-logger.ts     # Logs every request/response for learning
│   │
│   └── views/
│       ├── layout.html           # Shared HTML shell (minimal CSS, no framework)
│       ├── index.html            # Landing page — buttons for each auth method
│       ├── session/
│       │   ├── login.html        # Username/password form
│       │   └── profile.html      # Shows session data
│       ├── jwt/
│       │   ├── login.html        # Credentials form, displays tokens on success
│       │   └── protected.html    # Fetches protected endpoint, shows Bearer header
│       ├── apikey/
│       │   ├── generate.html     # Generate a key, shows it once
│       │   └── test.html         # Input field for key, calls protected endpoint
│       ├── magic/
│       │   ├── request.html      # Email input form
│       │   └── success.html      # Post-verification landing
│       ├── oidc/
│       │   ├── login.html        # "Sign in with Keycloak (OIDC)" button
│       │   └── profile.html      # Shows decoded ID token claims
│       ├── entra/
│       │   ├── login.html        # "Sign in with Entra ID" button
│       │   └── profile.html      # Shows groups, roles, tenant ID claims
│       ├── saml/
│       │   ├── login.html        # "Sign in via SAML" button
│       │   └── profile.html      # Shows decoded SAML assertion attributes
│       └── mtls/
│           └── test.html         # Instructions for testing with curl + client cert
```

## Auth Methods

Each method is fully isolated. Click its button on the landing page, walk through the flow, inspect everything.

---

### 1. Username & Password (Session-Based)

**Flow:**
```
Browser                         Express                         Redis
  │                                │                               │
  │  POST /auth/session/login      │                               │
  │  { email, password }           │                               │
  │ ──────────────────────────────>│                               │
  │                                │  bcrypt.compare(password,     │
  │                                │    stored_hash)               │
  │                                │                               │
  │                                │  SET session:{sid} user_data  │
  │                                │ ─────────────────────────────>│
  │                                │                               │
  │  Set-Cookie: sid=abc123;       │                               │
  │    HttpOnly; SameSite=Lax      │                               │
  │ <──────────────────────────────│                               │
  │                                │                               │
  │  GET /auth/session/profile     │                               │
  │  Cookie: sid=abc123            │                               │
  │ ──────────────────────────────>│                               │
  │                                │  GET session:{sid}            │
  │                                │ ─────────────────────────────>│
  │                                │  ← user_data                  │
  │  200 { user profile }          │                               │
  │ <──────────────────────────────│                               │
```

**What you'll see in the debug panel:** The `Set-Cookie` header, session ID, Redis key contents, bcrypt hash comparison.

**Key files:** `src/auth/session/handlers.ts`, `src/views/session/login.html`

---

### 2. JWT Authentication

**Flow:**
```
Browser                         Express
  │                                │
  │  POST /auth/jwt/login          │
  │  { email, password }           │
  │ ──────────────────────────────>│
  │                                │  Validate credentials
  │                                │  Sign access token (RS256, 15min)
  │                                │  Sign refresh token (HS256, 7d)
  │                                │
  │  200 { access_token }          │
  │  Set-Cookie: refresh=xyz;      │
  │    HttpOnly                    │
  │ <──────────────────────────────│
  │                                │
  │  GET /auth/jwt/protected       │
  │  Authorization: Bearer <token> │
  │ ──────────────────────────────>│
  │                                │  Verify signature + expiry
  │                                │  Decode payload
  │  200 { protected data }        │
  │ <──────────────────────────────│
```

**What you'll see in the debug panel:** The raw JWT (header.payload.signature), decoded payload, signature verification result, RS256 vs HS256 comparison side by side.

**Key files:** `src/auth/jwt/handlers.ts`

---

### 3. API Key Authentication

**Flow:**
```
Browser / curl                  Express                         SQLite
  │                                │                               │
  │  POST /auth/apikey/generate    │                               │
  │ ──────────────────────────────>│                               │
  │                                │  key = randomBytes(32)        │
  │                                │  hash = SHA-256(key)          │
  │                                │  INSERT hash, permissions     │
  │                                │ ─────────────────────────────>│
  │                                │                               │
  │  200 { api_key: "ak_..." }    │  ← shown ONCE, never stored   │
  │ <──────────────────────────────│    in plaintext               │
  │                                │                               │
  │  GET /auth/apikey/protected    │                               │
  │  X-API-Key: ak_...            │                               │
  │ ──────────────────────────────>│                               │
  │                                │  hash = SHA-256(provided_key) │
  │                                │  SELECT WHERE hash = ?        │
  │                                │ ─────────────────────────────>│
  │                                │  ← permissions                │
  │  200 { data }                  │                               │
  │ <──────────────────────────────│                               │
```

**What you'll see:** The generated key (once), the hashing process, Redis-based rate limit counter per key.

**Key files:** `src/auth/apikey/handlers.ts`

---

### 4. Magic Link (Passwordless Email)

**Flow:**
```
Browser                 Express                 Mailpit             SQLite
  │                        │                       │                   │
  │  POST /auth/magic/send │                       │                   │
  │  { email }             │                       │                   │
  │ ──────────────────────>│                       │                   │
  │                        │  token = sign({email}, │                   │
  │                        │    secret, 15min)      │                   │
  │                        │  INSERT token, used=0  │                   │
  │                        │ ──────────────────────────────────────────>│
  │                        │                       │                   │
  │                        │  SMTP: send link with │                   │
  │                        │    ?token=xxx          │                   │
  │                        │ ─────────────────────>│                   │
  │                        │                       │                   │
  │  200 "Check your email"│                       │                   │
  │ <──────────────────────│                       │                   │
  │                        │                       │                   │
  │  (Open Mailpit at :8025, click link)           │                   │
  │                        │                       │                   │
  │  GET /auth/magic/verify?token=xxx              │                   │
  │ ──────────────────────>│                       │                   │
  │                        │  Verify signature     │                   │
  │                        │  Check used=0         │                   │
  │                        │  UPDATE used=1        │                   │
  │                        │ ──────────────────────────────────────────>│
  │                        │  Create session        │                   │
  │  302 → /auth/magic/profile                     │                   │
  │ <──────────────────────│                       │                   │
```

**What you'll see:** The signed token URL, the email in Mailpit (http://localhost:8025), the single-use invalidation.

**Key files:** `src/auth/magic/handlers.ts`

---

### 5. OAuth 2.0 / OpenID Connect

**Flow:**
```
Browser                 Express                          Keycloak (oidc realm)
  │                        │                                    │
  │  GET /auth/oidc/login  │                                    │
  │ ──────────────────────>│                                    │
  │                        │  Generate state + PKCE             │
  │                        │    code_verifier → code_challenge  │
  │                        │  Store in session                  │
  │                        │                                    │
  │  302 → Keycloak /authorize                                  │
  │    ?client_id=...                                           │
  │    &redirect_uri=...                                        │
  │    &response_type=code                                      │
  │    &scope=openid profile email                              │
  │    &state=...                                               │
  │    &code_challenge=...                                      │
  │    &code_challenge_method=S256                              │
  │ ──────────────────────────────────────────────────────────>│
  │                        │                                    │
  │  (User logs in at Keycloak login page)                     │
  │                        │                                    │
  │  302 → /auth/oidc/callback?code=abc&state=xyz              │
  │ <──────────────────────────────────────────────────────────│
  │                        │                                    │
  │  GET /auth/oidc/callback?code=abc&state=xyz                │
  │ ──────────────────────>│                                    │
  │                        │  Verify state matches session      │
  │                        │  POST /token                       │
  │                        │    { code, code_verifier,          │
  │                        │      client_id, client_secret }    │
  │                        │ ──────────────────────────────────>│
  │                        │  ← { access_token, id_token }      │
  │                        │                                    │
  │                        │  Verify ID token signature         │
  │                        │  (fetch JWKS from Keycloak)        │
  │                        │  Decode claims                     │
  │                        │  Create session                    │
  │                        │                                    │
  │  302 → /auth/oidc/profile                                  │
  │ <──────────────────────│                                    │
```

**What you'll see:** The full `/authorize` URL being constructed, PKCE challenge/verifier pair, the authorization code in the callback, the token exchange POST, the decoded ID token, the JWKS verification.

**Keycloak realm:** `oidc` — client `auth-lab-oidc`, users `alice`/`password` and `bob`/`password`.

**Key files:** `src/auth/oidc/handlers.ts`

---

### 6. Entra ID SSO (Simulated)

Same OIDC flow as above, but Keycloak's `entra` realm is configured to mimic Microsoft Entra ID:

- Issuer URL follows Entra's pattern
- ID token includes `groups`, `roles`, `tid` (tenant ID) claims
- User `alice@contoso.local` is in group `Engineering` with role `Admin`

**What's different from OIDC:** The claims parsing. You'll see how Entra embeds group memberships and app roles in the token, and how you'd use those for authorization (e.g., "only users in the Engineering group can access this page").

**Production swap:** Replace the Keycloak discovery URL with `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` and update client credentials. Your code doesn't change.

**Key files:** `src/auth/entra/handlers.ts`

---

### 7. SAML 2.0

**Flow:**
```
Browser                 Express (SP)                     Keycloak (saml realm, IdP)
  │                        │                                    │
  │  GET /auth/saml/login  │                                    │
  │ ──────────────────────>│                                    │
  │                        │  Build AuthnRequest XML            │
  │                        │  Deflate + Base64 encode           │
  │                        │  Generate RelayState               │
  │                        │                                    │
  │  302 → Keycloak SSO endpoint                                │
  │    ?SAMLRequest=<base64 encoded XML>                        │
  │    &RelayState=...                                          │
  │ ──────────────────────────────────────────────────────────>│
  │                        │                                    │
  │  (User logs in at Keycloak login page)                     │
  │                        │                                    │
  │  Keycloak POSTs back to ACS URL:                           │
  │  POST /auth/saml/acs                                       │
  │    SAMLResponse=<base64 encoded signed XML assertion>       │
  │    RelayState=...                                           │
  │ <──────────────────────────────────────────────────────────│
  │                        │                                    │
  │  POST /auth/saml/acs   │                                    │
  │ ──────────────────────>│                                    │
  │                        │  Base64 decode SAMLResponse        │
  │                        │  Verify XML signature against      │
  │                        │    IdP certificate                 │
  │                        │  Parse assertion:                  │
  │                        │    NameID, attributes, conditions  │
  │                        │  Validate: not expired,            │
  │                        │    audience matches, etc.          │
  │                        │  Create session                    │
  │                        │                                    │
  │  302 → /auth/saml/profile                                  │
  │ <──────────────────────│                                    │
```

**What you'll see:** The raw AuthnRequest XML, the SAMLResponse XML (decoded), the X.509 signature verification, the extracted attributes. This is the most verbose flow — that's the point.

**Keycloak realm:** `saml` — client `auth-lab-saml`, user `alice`/`password`.

**Key files:** `src/auth/saml/handlers.ts`

---

### 8. Mutual TLS (mTLS) — Bonus

**Flow:**
```
curl (with client cert)        Express (HTTPS, separate port :3443)
  │                                │
  │  TLS Handshake                 │
  │  Client presents client.pem    │
  │  Server presents server.pem    │
  │ ──────────────────────────────>│
  │                                │  Verify client cert signed
  │                                │    by trusted CA (ca.pem)
  │                                │  Extract CN from cert
  │                                │
  │  GET /auth/mtls/protected      │
  │ ──────────────────────────────>│
  │                                │  req.socket.getPeerCertificate()
  │  200 { "identity": "client" }  │
  │ <──────────────────────────────│
```

**Test with:**
```bash
curl --cert shared/certs/client.pem --key shared/certs/client-key.pem \
     --cacert shared/certs/ca.pem \
     https://localhost:3443/auth/mtls/protected
```

**Key files:** `src/auth/mtls/handlers.ts`

---

## Debug Panel

Every HTML page includes a collapsible debug panel at the bottom that shows:

- **Request:** method, URL, headers sent
- **Response:** status, headers received (especially `Set-Cookie`, `Authorization`)
- **Tokens:** raw + decoded JWT, SAML assertion XML, session contents
- **Timeline:** each HTTP request in the flow with timestamps

This is the main learning tool. It turns invisible protocol exchanges into something you can read.

---

## Keycloak Realms

| Realm | Simulates | Protocol | Users | Special Config |
|---|---|---|---|---|
| `oidc` | Google / GitHub | OpenID Connect | `alice`/`password`, `bob`/`password` | Standard OIDC scopes |
| `entra` | Microsoft Entra ID | OIDC | `alice@contoso.local`/`password` | `groups`, `roles`, `tid` claims, group `Engineering` |
| `saml` | Enterprise SAML IdP | SAML 2.0 | `alice`/`password` | Signed assertions, attribute mapping |

**Admin Console:** http://localhost:8080 — `admin`/`admin`

Realms are auto-imported from `keycloak/realm-exports/` on first startup.

---

## Quick Start

### Prerequisites
- Docker and Docker Compose

That's it. Everything else runs in containers.

### Setup

```bash
git clone <repo-url> && cd auth-methods-lab

# Generate RSA keypair for JWT RS256 signing
mkdir -p shared/keys
openssl genrsa -out shared/keys/private.pem 2048
openssl rsa -in shared/keys/private.pem -pubout -out shared/keys/public.pem

# Generate self-signed certs for mTLS
mkdir -p shared/certs
openssl req -x509 -newkey rsa:2048 -keyout shared/certs/ca-key.pem -out shared/certs/ca.pem \
  -days 365 -nodes -subj "/CN=Auth Lab CA"
openssl req -newkey rsa:2048 -keyout shared/certs/server-key.pem -out shared/certs/server.csr \
  -nodes -subj "/CN=localhost"
openssl x509 -req -in shared/certs/server.csr -CA shared/certs/ca.pem -CAkey shared/certs/ca-key.pem \
  -CAcreateserial -out shared/certs/server.pem -days 365
openssl req -newkey rsa:2048 -keyout shared/certs/client-key.pem -out shared/certs/client.csr \
  -nodes -subj "/CN=client"
openssl x509 -req -in shared/certs/client.csr -CA shared/certs/ca.pem -CAkey shared/certs/ca-key.pem \
  -CAcreateserial -out shared/certs/client.pem -days 365

# Start everything
docker compose up --build
```

### Services

| Service | URL | Purpose |
|---|---|---|
| App | http://localhost:3000 | Landing page + all auth flows |
| App (mTLS) | https://localhost:3443 | mTLS-only HTTPS endpoint |
| Keycloak | http://localhost:8080 | Identity Provider admin |
| Mailpit | http://localhost:8025 | Magic link email inbox |
| Redis | localhost:6379 | Sessions + rate limits |
| Postgres | localhost:5432 | Keycloak data |
| SQLite | (embedded) | App user data, API keys, magic tokens |

---

## Implementation Order

| Order | Method | You'll Learn | Time Estimate |
|---|---|---|---|
| 1 | Username & Password | Sessions, cookies, password hashing, CSRF | 1-2 hours |
| 2 | JWT Auth | Token signing (HS256/RS256), refresh rotation, stateless vs stateful | 2-3 hours |
| 3 | API Key | Hashed secret storage, rate limiting, permission scoping | 1-2 hours |
| 4 | Magic Link | Signed URLs, single-use tokens, SMTP, email security | 1-2 hours |
| 5 | OAuth 2.0 / OIDC | Authorization Code + PKCE, token exchange, JWKS, ID tokens | 3-4 hours |
| 6 | Entra ID | Enterprise OIDC, group/role claims, tenant isolation | 1-2 hours (builds on #5) |
| 7 | SAML 2.0 | XML signatures, SP/IdP metadata, assertion parsing, certificate trust | 3-4 hours |
| 8 | mTLS | Transport-layer auth, client certificates, CA trust chains | 1-2 hours |

---

## Per-Method Deliverables

For each auth method, the implementation should include:

1. **`routes.ts`** — Express route handlers, heavily commented
2. **`handlers.ts`** — Core auth logic, no abstraction, every step explicit
3. **`NOTES.md`** — Mermaid sequence diagram, security pitfalls, "what to watch out for in prod"
4. **HTML pages** — Minimal UI that makes the flow visible (forms, token displays, debug info)

---

## Moving to Production

| Auth Method | What Changes |
|---|---|
| OAuth 2.0 (Google) | Swap Keycloak discovery URL → Google's, register app in Google Cloud Console |
| OAuth 2.0 (GitHub) | Swap Keycloak discovery URL → GitHub's, register OAuth app on GitHub |
| Entra ID | Swap Keycloak URL → `https://login.microsoftonline.com/{tenant}/v2.0`, register in Azure portal |
| SAML 2.0 | Swap Keycloak metadata → real IdP metadata, exchange production certs |
| JWT / Sessions | Rotate secrets, enforce HTTPS, set `Secure` cookie flag |
| API Keys | Same pattern — just use a real database |
| Magic Link | Swap Mailpit SMTP for SES / Postmark / Resend |
| mTLS | Use CA-signed certs, terminate at load balancer |

---

## Environment Variables

```bash
# Server
PORT=3000
MTLS_PORT=3443
NODE_ENV=development

# Database
REDIS_URL=redis://redis:6379

# JWT
JWT_SECRET=local-dev-jwt-secret-change-in-prod
JWT_PRIVATE_KEY_PATH=/app/shared/keys/private.pem
JWT_PUBLIC_KEY_PATH=/app/shared/keys/public.pem
JWT_ACCESS_EXPIRY=15m
JWT_REFRESH_EXPIRY=7d

# Sessions
SESSION_SECRET=local-dev-session-secret-change-in-prod

# Keycloak — OIDC realm (mimics Google/GitHub)
OIDC_ISSUER=http://keycloak:8080/realms/oidc
OIDC_CLIENT_ID=auth-lab-oidc
OIDC_CLIENT_SECRET=change-me-after-realm-import

# Keycloak — Entra realm (mimics Azure AD)
ENTRA_ISSUER=http://keycloak:8080/realms/entra
ENTRA_CLIENT_ID=auth-lab-entra
ENTRA_CLIENT_SECRET=change-me-after-realm-import

# Keycloak — SAML realm
SAML_IDP_METADATA_URL=http://keycloak:8080/realms/saml/protocol/saml/descriptor
SAML_SP_ENTITY_ID=auth-methods-lab
SAML_ACS_URL=http://localhost:3000/auth/saml/acs

# Email (Mailpit)
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_FROM=auth-lab@localhost

# mTLS
MTLS_CA_PATH=/app/shared/certs/ca.pem
MTLS_SERVER_CERT_PATH=/app/shared/certs/server.pem
MTLS_SERVER_KEY_PATH=/app/shared/certs/server-key.pem
```

## Tech Stack

| Tool | Why |
|---|---|
| **Express + TypeScript** | Thin enough that auth logic is the focus, not framework magic |
| **Plain HTML + vanilla JS** | See every form POST, every redirect, every header — no framework abstraction |
| **Keycloak** | Production-grade IdP that speaks OIDC and SAML, simulates Entra/Google/GitHub |
| **Redis** | Session store, token blacklist, rate limiting |
| **SQLite** | Zero-config DB for users, API keys, magic link tokens |
| **Mailpit** | Local SMTP catch-all with web UI — see every email at :8025 |
| **Docker Compose** | One command, everything runs |

