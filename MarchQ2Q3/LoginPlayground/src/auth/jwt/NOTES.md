# JWT Authentication

## Flow Diagram

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as Express Server
    participant DB as SQLite
    participant R as Redis

    B->>S: POST /auth/jwt/login {email, password}
    S->>DB: SELECT password_hash WHERE email=?
    S->>S: bcrypt.compare()
    S->>S: jwt.sign(payload, PRIVATE_KEY, RS256) → access_token
    S->>S: jwt.sign(payload, SECRET, HS256) → refresh_token
    S-->>B: 200 {access_token} + Set-Cookie: refresh_token (HttpOnly)

    B->>S: GET /auth/jwt/protected
    Note over B: Authorization: Bearer <access_token>
    S->>S: jwt.verify(token, PUBLIC_KEY, RS256)
    S-->>B: 200 {protected data}

    Note over B,S: When access token expires...
    B->>S: POST /auth/jwt/refresh (Cookie: refresh_token)
    S->>S: jwt.verify(refresh_token, SECRET, HS256)
    S->>R: Check blacklist (jwt:blacklist:{token})
    S->>R: Blacklist old refresh token
    S->>S: Sign new access + refresh tokens
    S-->>B: 200 {new_access_token} + Set-Cookie: new_refresh_token
```

## RS256 vs HS256

| | RS256 (Access Token) | HS256 (Refresh Token) |
|---|---|---|
| **Type** | Asymmetric | Symmetric |
| **Sign with** | Private key | Shared secret |
| **Verify with** | Public key | Same shared secret |
| **Who can verify** | Anyone with the public key | Only the auth server |
| **Use case** | Tokens verified by multiple services | Tokens only handled by auth server |

## Token Rotation

When a refresh token is used, the old one is blacklisted in Redis and a new pair is issued. This limits the damage if a refresh token is stolen — it can only be used once.

## Security Notes

- Access tokens are short-lived (15min) — limits exposure window
- Refresh tokens are in HttpOnly cookies — can't be stolen via XSS
- RS256 lets microservices verify tokens without knowing the signing secret
- Token rotation detects theft: if an attacker uses a stolen refresh token, the legitimate user's next refresh fails (token already used)

## What to Watch Out for in Production

| Concern | Dev (this lab) | Production |
|---------|---------------|------------|
| Key storage | Files on disk | HSM / Vault / KMS |
| Key rotation | Manual | Automated with JWKS endpoint |
| Token storage (client) | In-memory variable | In-memory only (NEVER localStorage) |
| Refresh token cookie | `Secure: false` | `Secure: true` (HTTPS only) |
| Token revocation | Redis blacklist | Redis cluster with TTL |
| Algorithm confusion | Hardcoded RS256 | Always specify algorithm in verify() |
