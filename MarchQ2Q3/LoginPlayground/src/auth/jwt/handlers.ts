import type { Request, Response } from "express";
import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";
import fs from "node:fs";
import db from "../../db.js";
import redis from "../../redis.js";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── Keys ──

const JWT_SECRET = process.env.JWT_SECRET || "dev-jwt-secret";
const PRIVATE_KEY_PATH = process.env.JWT_PRIVATE_KEY_PATH || "./shared/keys/private.pem";
const PUBLIC_KEY_PATH = process.env.JWT_PUBLIC_KEY_PATH || "./shared/keys/public.pem";
const ACCESS_EXPIRY = process.env.JWT_ACCESS_EXPIRY || "15m";
const REFRESH_EXPIRY = process.env.JWT_REFRESH_EXPIRY || "7d";

function getPrivateKey(): string {
  return fs.readFileSync(PRIVATE_KEY_PATH, "utf-8");
}

function getPublicKey(): string {
  return fs.readFileSync(PUBLIC_KEY_PATH, "utf-8");
}

// ── Types ──

interface UserRow {
  id: string;
  email: string;
  password_hash: string;
}

interface JwtPayload {
  sub: string;
  email: string;
  iat?: number;
  exp?: number;
}

// ── GET /auth/jwt/login ──

export function showLoginPage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "JWT Login",
      `
    <h1>JWT Authentication</h1>
    <p>Enter credentials. The server signs an access token with <strong>RS256</strong> (asymmetric) and a refresh token with <strong>HS256</strong> (symmetric).</p>

    <form method="POST" action="/auth/jwt/login">
      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" value="alice@example.com" required>
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" value="password" required>
      </div>
      <button type="submit">Log In</button>
    </form>

    <div class="alert alert-info" style="margin-top:1rem">
      <strong>Test credentials:</strong> alice@example.com / password
    </div>
    `
    )
  );
}

// ── POST /auth/jwt/login ──
// 1. Validate credentials against SQLite
// 2. Sign access token with RS256 (private key, 15min)
// 3. Sign refresh token with HS256 (shared secret, 7d)
// 4. Return access token in response body, refresh token in HttpOnly cookie

export async function handleLogin(req: Request, res: Response): Promise<void> {
  const { email, password } = req.body as { email: string; password: string };

  addDebug(res, "Step 1: Received credentials", `email=${email}`);

  // Validate credentials
  const user = db.prepare("SELECT id, email, password_hash FROM users WHERE email = ?").get(email) as
    | UserRow
    | undefined;

  if (!user) {
    addDebug(res, "Step 2: User lookup", `No user found: ${email}`, "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(html("Login Failed", `<h1>Login Failed</h1><div class="alert alert-error">Invalid credentials.</div><a href="/auth/jwt/login" class="btn">Try Again</a>`));
    return;
  }

  const match = await bcrypt.compare(password, user.password_hash);
  if (!match) {
    addDebug(res, "Step 2: Password check", "bcrypt.compare() returned false", "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(html("Login Failed", `<h1>Login Failed</h1><div class="alert alert-error">Invalid credentials.</div><a href="/auth/jwt/login" class="btn">Try Again</a>`));
    return;
  }

  addDebug(res, "Step 2: Credentials valid", `User: ${user.id} (${user.email})`, "success");

  // Sign access token with RS256 (asymmetric)
  const accessPayload: JwtPayload = { sub: user.id, email: user.email };
  const accessToken = jwt.sign(accessPayload, getPrivateKey(), {
    algorithm: "RS256",
    expiresIn: ACCESS_EXPIRY,
  });

  addDebug(
    res,
    "Step 3: Access token signed (RS256)",
    `Algorithm: RS256 (asymmetric — signed with private key, verified with public key)\n` +
      `Expiry: ${ACCESS_EXPIRY}\n` +
      `Payload: ${JSON.stringify(accessPayload)}\n\n` +
      `Raw token:\n${accessToken}`,
    "code"
  );

  // Sign refresh token with HS256 (symmetric)
  const refreshPayload = { sub: user.id, type: "refresh" };
  const refreshToken = jwt.sign(refreshPayload, JWT_SECRET, {
    algorithm: "HS256",
    expiresIn: REFRESH_EXPIRY,
  });

  addDebug(
    res,
    "Step 4: Refresh token signed (HS256)",
    `Algorithm: HS256 (symmetric — same secret for sign and verify)\n` +
      `Expiry: ${REFRESH_EXPIRY}\n` +
      `Stored in HttpOnly cookie (not accessible to JavaScript)\n\n` +
      `Raw token:\n${refreshToken}`,
    "code"
  );

  addDebug(
    res,
    "Step 5: RS256 vs HS256",
    `RS256 (access token):\n` +
      `  - Asymmetric: private key signs, public key verifies\n` +
      `  - Any service with the public key can verify without the signing secret\n` +
      `  - Used for access tokens that multiple services need to verify\n\n` +
      `HS256 (refresh token):\n` +
      `  - Symmetric: same secret for signing and verifying\n` +
      `  - Simpler but the secret must be kept on the auth server only\n` +
      `  - Used for refresh tokens that only the auth server handles`,
    "info"
  );

  // Set refresh token as HttpOnly cookie
  res.cookie("refresh_token", refreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: false,
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    path: "/auth/jwt",
  });

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "JWT Tokens Issued",
      `
    <h1>JWT Tokens Issued</h1>
    <div class="alert alert-success">Login successful. Two tokens have been issued.</div>

    <h2>Access Token (RS256)</h2>
    <p>Send this in the <code>Authorization: Bearer &lt;token&gt;</code> header to access protected resources.</p>
    <div class="token-display">
      <h4>Raw Token</h4>
      <pre id="access-raw">${accessToken}</pre>
    </div>
    <div id="access-decoded"></div>

    <h2>Refresh Token (HS256)</h2>
    <p>Stored in an HttpOnly cookie. You can't see it in JavaScript — check the debug panel below.</p>

    <div style="margin-top:1.5rem">
      <a href="/auth/jwt/protected" class="btn btn-blue"
         onclick="event.preventDefault(); fetchProtected();">
        Access Protected Resource
      </a>
      <button onclick="refreshTokens()" class="btn" style="margin-left:0.5rem">Refresh Tokens</button>
    </div>

    <div id="protected-result" style="margin-top:1rem"></div>

    <script>
      // Decode and display the access token
      renderDecodedJwt('access-decoded', '${accessToken}');

      // Store access token in memory (not localStorage — that's insecure)
      let currentAccessToken = '${accessToken}';

      async function fetchProtected() {
        const result = document.getElementById('protected-result');
        try {
          const resp = await fetch('/auth/jwt/protected', {
            headers: { 'Authorization': 'Bearer ' + currentAccessToken }
          });
          const text = await resp.text();
          result.innerHTML = '<h3>Response:</h3>' + text;
        } catch (err) {
          result.innerHTML = '<div class="alert alert-error">' + err.message + '</div>';
        }
      }

      async function refreshTokens() {
        const result = document.getElementById('protected-result');
        try {
          const resp = await fetch('/auth/jwt/refresh', { method: 'POST' });
          const data = await resp.json();
          if (data.access_token) {
            currentAccessToken = data.access_token;
            document.getElementById('access-raw').textContent = data.access_token;
            renderDecodedJwt('access-decoded', data.access_token);
            result.innerHTML = '<div class="alert alert-success">Tokens refreshed. New access token issued.</div>';
          } else {
            result.innerHTML = '<div class="alert alert-error">' + (data.error || 'Refresh failed') + '</div>';
          }
        } catch (err) {
          result.innerHTML = '<div class="alert alert-error">' + err.message + '</div>';
        }
      }
    </script>
    `
    )
  );
}

// ── POST /auth/jwt/refresh ──
// 1. Read refresh token from HttpOnly cookie
// 2. Verify signature and check if blacklisted
// 3. Blacklist old refresh token in Redis
// 4. Issue new access + refresh token pair

export async function handleRefresh(req: Request, res: Response): Promise<void> {
  const refreshToken = req.cookies?.refresh_token;

  if (!refreshToken) {
    addDebug(res, "Refresh: No token", "No refresh_token cookie found", "error");
    res.status(401).json({ error: "No refresh token" });
    return;
  }

  addDebug(res, "Step 1: Refresh token from cookie", `Token: ${refreshToken.slice(0, 30)}...`, "info");

  // Check if token is blacklisted
  const isBlacklisted = await redis.get(`jwt:blacklist:${refreshToken}`);
  if (isBlacklisted) {
    addDebug(res, "Step 2: Blacklist check", "This refresh token has been revoked!", "error");
    res.status(401).json({ error: "Refresh token revoked" });
    return;
  }

  // Verify refresh token
  let decoded: JwtPayload;
  try {
    decoded = jwt.verify(refreshToken, JWT_SECRET) as JwtPayload;
  } catch (err) {
    addDebug(res, "Step 2: Verify failed", `Error: ${(err as Error).message}`, "error");
    res.status(401).json({ error: "Invalid refresh token" });
    return;
  }

  addDebug(res, "Step 2: Refresh token verified", `User: ${decoded.sub}`, "success");

  // Blacklist the old refresh token (token rotation)
  await redis.set(`jwt:blacklist:${refreshToken}`, "1", "EX", 7 * 24 * 60 * 60);
  addDebug(
    res,
    "Step 3: Old token blacklisted",
    `Redis key: jwt:blacklist:${refreshToken.slice(0, 20)}...\n` +
      `This prevents reuse of the old refresh token (token rotation).`,
    "warning"
  );

  // Look up user for fresh claims
  const user = db.prepare("SELECT id, email FROM users WHERE id = ?").get(decoded.sub) as
    | { id: string; email: string }
    | undefined;

  if (!user) {
    res.status(401).json({ error: "User not found" });
    return;
  }

  // Issue new pair
  const newAccessToken = jwt.sign({ sub: user.id, email: user.email }, getPrivateKey(), {
    algorithm: "RS256",
    expiresIn: ACCESS_EXPIRY,
  });

  const newRefreshToken = jwt.sign({ sub: user.id, type: "refresh" }, JWT_SECRET, {
    algorithm: "HS256",
    expiresIn: REFRESH_EXPIRY,
  });

  res.cookie("refresh_token", newRefreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: false,
    maxAge: 7 * 24 * 60 * 60 * 1000,
    path: "/auth/jwt",
  });

  addDebug(
    res,
    "Step 4: New token pair issued",
    `New access token: ${newAccessToken.slice(0, 30)}...\nNew refresh token in HttpOnly cookie`,
    "success"
  );

  res.json({ access_token: newAccessToken });
}

// ── GET /auth/jwt/protected ──
// Verifies the Bearer token from the Authorization header.

export function showProtected(req: Request, res: Response): void {
  const authHeader = req.headers.authorization;

  addDebug(res, "Step 1: Authorization header", authHeader || "(missing)", authHeader ? "info" : "error");

  if (!authHeader?.startsWith("Bearer ")) {
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Unauthorized", `
        <h1>Unauthorized</h1>
        <div class="alert alert-error">Missing or invalid Authorization header. Expected: <code>Bearer &lt;token&gt;</code></div>
        <a href="/auth/jwt/login" class="btn">Log In</a>
      `)
    );
    return;
  }

  const token = authHeader.slice(7);
  addDebug(res, "Step 2: Extracted token", `${token.slice(0, 50)}...`, "code");

  // Verify with public key (RS256)
  let decoded: JwtPayload;
  try {
    decoded = jwt.verify(token, getPublicKey(), { algorithms: ["RS256"] }) as JwtPayload;
  } catch (err) {
    addDebug(res, "Step 3: Verification failed", `Error: ${(err as Error).message}`, "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Invalid Token", `
        <h1>Invalid Token</h1>
        <div class="alert alert-error">${(err as Error).message}</div>
        <a href="/auth/jwt/login" class="btn">Log In</a>
      `)
    );
    return;
  }

  addDebug(
    res,
    "Step 3: Token verified (RS256)",
    `Verified using PUBLIC key (not the private key that signed it).\n` +
      `Any service with the public key can verify this token.\n\n` +
      `Decoded payload: ${JSON.stringify(decoded, null, 2)}`,
    "success"
  );

  res.setHeader("content-type", "text/html");
  res.send(`
    <div class="alert alert-success">Access granted via JWT Bearer token.</div>
    <table>
      <tr><th>Claim</th><th>Value</th></tr>
      <tr><td>sub (user ID)</td><td>${decoded.sub}</td></tr>
      <tr><td>email</td><td>${decoded.email}</td></tr>
      <tr><td>iat (issued at)</td><td>${new Date((decoded.iat || 0) * 1000).toISOString()}</td></tr>
      <tr><td>exp (expires)</td><td>${new Date((decoded.exp || 0) * 1000).toISOString()}</td></tr>
    </table>
  `);
}
