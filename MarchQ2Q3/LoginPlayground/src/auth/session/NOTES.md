# Session-Based Authentication (Username & Password)

## Flow Diagram

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as Express Server
    participant DB as SQLite
    participant R as Redis

    B->>S: POST /auth/session/login {email, password}
    S->>DB: SELECT password_hash WHERE email=?
    DB-->>S: password_hash (bcrypt)
    S->>S: bcrypt.compare(password, hash)
    S->>R: SET sess:{sid} {userId, email}
    R-->>S: OK
    S-->>B: 302 /profile + Set-Cookie: connect.sid=abc; HttpOnly; SameSite=Lax

    B->>S: GET /auth/session/profile (Cookie: connect.sid=abc)
    S->>R: GET sess:{sid}
    R-->>S: {userId, email}
    S-->>B: 200 Profile page

    B->>S: POST /auth/session/logout (Cookie: connect.sid=abc)
    S->>R: DEL sess:{sid}
    S-->>B: 302 /login + Set-Cookie: connect.sid=; Expires=past
```

## How It Works

1. **User submits credentials** — a plain HTML form POSTs email + password
2. **Server looks up user** — queries SQLite for the bcrypt hash
3. **bcrypt.compare()** — compares plaintext against the stored hash. The hash includes the salt, so no separate salt column is needed
4. **Session created** — express-session generates a random session ID, stores user data in Redis under key `sess:{sid}`
5. **Cookie set** — the session ID is sent back in a `Set-Cookie` header with `HttpOnly` (JavaScript can't read it) and `SameSite=Lax` (basic CSRF protection)
6. **Subsequent requests** — the browser automatically sends the cookie. The server loads session data from Redis using the session ID
7. **Logout** — deletes the Redis key and clears the cookie

## Security Notes

- **bcrypt** is intentionally slow (~100ms per hash). This makes brute-force attacks expensive
- **HttpOnly** cookies prevent XSS attacks from stealing session IDs
- **SameSite=Lax** prevents the most common CSRF attacks (form POSTs from other sites)
- Session IDs are cryptographically random — they can't be guessed
- Sessions expire after 30 minutes of inactivity (configurable)

## What to Watch Out for in Production

| Concern | Dev (this lab) | Production |
|---------|---------------|------------|
| Cookie `Secure` flag | `false` (HTTP) | `true` (HTTPS only) |
| Session secret | Hardcoded | Env var, rotated regularly |
| bcrypt rounds | 10 | 12-14 (balance security vs. latency) |
| Rate limiting | None | Add per-IP and per-account limits |
| CSRF tokens | Not implemented | Add `csurf` or double-submit cookie |
| Password requirements | None | Min length, complexity rules |
| Account lockout | None | Lock after N failed attempts |
