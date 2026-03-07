import type { Request, Response } from "express";
import bcrypt from "bcrypt";
import db from "../../db.js";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── Types ──

interface UserRow {
  id: string;
  email: string;
  password_hash: string;
}

// Session types are in src/types/session.d.ts

// ── GET /auth/session/login ──
// Shows the login form. Nothing fancy — just a form that POSTs credentials.

export function showLoginPage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Session Login",
      `
    <h1>Username & Password (Session-Based)</h1>
    <p>Enter credentials. The server will verify with bcrypt, create a Redis session, and set an HttpOnly cookie.</p>

    <form method="POST" action="/auth/session/login">
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

// ── POST /auth/session/login ──
// 1. Look up user by email in SQLite
// 2. Compare password with bcrypt hash
// 3. Create Redis session (via express-session)
// 4. Set HttpOnly session cookie

export async function handleLogin(req: Request, res: Response): Promise<void> {
  const { email, password } = req.body as { email: string; password: string };

  addDebug(res, "Step 1: Received credentials", `email=${email}, password=***`);

  // Step 1: Look up user in SQLite
  const user = db.prepare("SELECT id, email, password_hash FROM users WHERE email = ?").get(email) as
    | UserRow
    | undefined;

  if (!user) {
    addDebug(res, "Step 2: User lookup", `No user found with email: ${email}`, "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Login Failed", `
        <h1>Login Failed</h1>
        <div class="alert alert-error">No user found with that email.</div>
        <a href="/auth/session/login" class="btn">Try Again</a>
      `)
    );
    return;
  }

  addDebug(res, "Step 2: User lookup", `Found user: id=${user.id}, email=${user.email}`, "success");
  addDebug(res, "Step 2b: Stored hash", user.password_hash, "code");

  // Step 2: Compare password with bcrypt hash
  const startTime = Date.now();
  const match = await bcrypt.compare(password, user.password_hash);
  const elapsed = Date.now() - startTime;

  addDebug(
    res,
    "Step 3: bcrypt.compare()",
    `Result: ${match} (took ${elapsed}ms)\n` +
      `bcrypt compares the plaintext password against the stored hash.\n` +
      `The hash includes the salt, so no separate salt lookup is needed.`,
    match ? "success" : "error"
  );

  if (!match) {
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Login Failed", `
        <h1>Login Failed</h1>
        <div class="alert alert-error">Invalid password.</div>
        <a href="/auth/session/login" class="btn">Try Again</a>
      `)
    );
    return;
  }

  // Step 3: Create session (express-session writes to Redis automatically)
  req.session.userId = user.id;
  req.session.email = user.email;
  req.session.authMethod = "session";

  addDebug(
    res,
    "Step 4: Session created",
    `Session ID: ${req.sessionID}\n` +
      `Stored in Redis key: sess:${req.sessionID}\n` +
      `Data: { userId: "${user.id}", email: "${user.email}" }`,
    "success"
  );

  addDebug(
    res,
    "Step 5: Set-Cookie header",
    `The response includes a Set-Cookie header with the session ID.\n` +
      `Flags: HttpOnly (JS can't read it), SameSite=Lax (CSRF protection).\n` +
      `The browser sends this cookie automatically on every subsequent request.`,
    "info"
  );

  // Redirect to profile
  res.redirect("/auth/session/profile");
}

// ── GET /auth/session/profile ──
// Reads the session from Redis (via the cookie) and shows user data.

export function showProfile(req: Request, res: Response): void {
  if (!req.session.userId) {
    addDebug(res, "Session check", "No active session found. Cookie missing or expired.", "warning");
    res.redirect("/auth/session/login");
    return;
  }

  addDebug(
    res,
    "Session loaded from Redis",
    `Session ID: ${req.sessionID}\n` +
      `Redis key: sess:${req.sessionID}\n` +
      `Data: ${JSON.stringify({ userId: req.session.userId, email: req.session.email })}`,
    "success"
  );

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Session Profile",
      `
    <h1>Session-Based Auth — Profile</h1>
    <div class="alert alert-success">You are authenticated via session cookie.</div>

    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>User ID</td><td>${req.session.userId}</td></tr>
      <tr><td>Email</td><td>${req.session.email}</td></tr>
      <tr><td>Session ID</td><td><code>${req.sessionID}</code></td></tr>
      <tr><td>Auth Method</td><td>${req.session.authMethod}</td></tr>
    </table>

    <form method="POST" action="/auth/session/logout" style="margin-top:1rem">
      <button type="submit" class="btn-danger">Log Out</button>
    </form>
    `
    )
  );
}

// ── POST /auth/session/logout ──
// Destroys the Redis session and clears the cookie.

export function handleLogout(req: Request, res: Response): void {
  const sid = req.sessionID;

  addDebug(
    res,
    "Logout: Destroying session",
    `Session ID: ${sid}\n` +
      `This deletes the Redis key sess:${sid} and clears the cookie.`,
    "warning"
  );

  req.session.destroy((err) => {
    if (err) {
      console.error("Session destroy error:", err);
    }
    res.clearCookie("connect.sid");
    res.redirect("/auth/session/login");
  });
}
