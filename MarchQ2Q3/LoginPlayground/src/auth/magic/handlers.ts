import type { Request, Response } from "express";
import jwt from "jsonwebtoken";
import nodemailer from "nodemailer";
import { v4 as uuidv4 } from "uuid";
import db from "../../db.js";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

const JWT_SECRET = process.env.JWT_SECRET || "dev-jwt-secret";
const SMTP_HOST = process.env.SMTP_HOST || "localhost";
const SMTP_PORT = parseInt(process.env.SMTP_PORT || "1025", 10);
const SMTP_FROM = process.env.SMTP_FROM || "auth-lab@localhost";
const APP_URL = `http://localhost:${process.env.PORT || "3000"}`;

// ── SMTP transport (Mailpit) ──

const transporter = nodemailer.createTransport({
  host: SMTP_HOST,
  port: SMTP_PORT,
  secure: false,
});

// ── GET /auth/magic/request ──

export function showRequestPage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Magic Link",
      `
    <h1>Magic Link (Passwordless Email)</h1>
    <p>Enter your email. A one-time login link will be sent. No password needed.</p>

    <form method="POST" action="/auth/magic/send">
      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" value="alice@example.com" required>
      </div>
      <button type="submit">Send Magic Link</button>
    </form>

    <div class="alert alert-info" style="margin-top:1rem">
      <strong>Tip:</strong> After sending, check <a href="http://localhost:8025" target="_blank">Mailpit (localhost:8025)</a> to see the email.
    </div>
    `
    )
  );
}

// ── POST /auth/magic/send ──
// 1. Generate a signed JWT with the email claim (15min expiry)
// 2. Store the token in SQLite (used=0)
// 3. Send email with the magic link via SMTP (Mailpit)

export async function handleSend(req: Request, res: Response): Promise<void> {
  const { email } = req.body as { email: string };

  addDebug(res, "Step 1: Received email", email);

  // Sign a JWT with the email (acts as the magic link token)
  const token = jwt.sign({ email, type: "magic" }, JWT_SECRET, { expiresIn: "15m" });

  addDebug(
    res,
    "Step 2: Token signed",
    `jwt.sign({ email: "${email}", type: "magic" }, secret, { expiresIn: "15m" })\n\n` +
      `Token: ${token}`,
    "code"
  );

  // Store in SQLite for single-use tracking
  const id = uuidv4();
  const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
  db.prepare("INSERT INTO magic_tokens (id, token, email, used, expires_at) VALUES (?, ?, ?, 0, ?)").run(
    id,
    token,
    email,
    expiresAt
  );

  addDebug(
    res,
    "Step 3: Token stored in SQLite",
    `INSERT INTO magic_tokens (id, token, email, used, expires_at)\n` +
      `VALUES ('${id}', '${token.slice(0, 30)}...', '${email}', 0, '${expiresAt}')\n\n` +
      `The 'used' flag ensures single-use: once clicked, the token can't be reused.`,
    "success"
  );

  // Build the magic link URL
  const magicLink = `${APP_URL}/auth/magic/verify?token=${encodeURIComponent(token)}`;

  addDebug(res, "Step 4: Magic link URL", magicLink, "code");

  // Send email via Mailpit
  try {
    await transporter.sendMail({
      from: SMTP_FROM,
      to: email,
      subject: "Your Magic Link — Auth Methods Lab",
      text: `Click this link to log in:\n\n${magicLink}\n\nThis link expires in 15 minutes and can only be used once.`,
      html: `
        <h2>Auth Methods Lab</h2>
        <p>Click the button below to log in:</p>
        <p><a href="${magicLink}" style="display:inline-block;padding:12px 24px;background:#238636;color:white;text-decoration:none;border-radius:6px;font-family:monospace;">Log In</a></p>
        <p style="color:#888;font-size:12px;">This link expires in 15 minutes and can only be used once.</p>
        <p style="color:#888;font-size:12px;">Raw link: ${magicLink}</p>
      `,
    });

    addDebug(
      res,
      "Step 5: Email sent via SMTP",
      `To: ${email}\nFrom: ${SMTP_FROM}\nSMTP: ${SMTP_HOST}:${SMTP_PORT}\n\n` +
        `Check Mailpit at http://localhost:8025 to see the email.`,
      "success"
    );
  } catch (err) {
    addDebug(res, "Step 5: Email send failed", (err as Error).message, "error");
  }

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Check Your Email",
      `
    <h1>Check Your Email</h1>
    <div class="alert alert-success">
      A magic link has been sent to <strong>${email}</strong>.
    </div>
    <p>
      Open <a href="http://localhost:8025" target="_blank">Mailpit (localhost:8025)</a> to see the email and click the link.
    </p>
    <p>The link expires in 15 minutes and can only be used once.</p>
    `
    )
  );
}

// ── GET /auth/magic/verify?token=xxx ──
// 1. Verify JWT signature
// 2. Check that the token hasn't been used (used=0)
// 3. Mark the token as used (used=1)
// 4. Create a session

export function handleVerify(req: Request, res: Response): void {
  const token = req.query.token as string | undefined;

  if (!token) {
    res.setHeader("content-type", "text/html");
    res.status(400).send(html("Invalid Link", `<h1>Invalid Link</h1><div class="alert alert-error">Missing token.</div>`));
    return;
  }

  addDebug(res, "Step 1: Token from URL", `${token.slice(0, 50)}...`, "code");

  // Verify JWT signature and expiry
  let decoded: { email: string; type: string };
  try {
    decoded = jwt.verify(token, JWT_SECRET) as { email: string; type: string };
  } catch (err) {
    addDebug(res, "Step 2: Token verification failed", (err as Error).message, "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Invalid Token", `
        <h1>Invalid or Expired Link</h1>
        <div class="alert alert-error">${(err as Error).message}</div>
        <a href="/auth/magic/request" class="btn">Request New Link</a>
      `)
    );
    return;
  }

  addDebug(
    res,
    "Step 2: Token verified",
    `Decoded: ${JSON.stringify(decoded)}\nSignature valid, not expired.`,
    "success"
  );

  // Check single-use: look up in SQLite
  const row = db
    .prepare("SELECT id, used FROM magic_tokens WHERE token = ?")
    .get(token) as { id: string; used: number } | undefined;

  if (!row) {
    addDebug(res, "Step 3: Token not found in DB", "Token doesn't exist in magic_tokens table.", "error");
    res.setHeader("content-type", "text/html");
    res.status(401).send(html("Invalid Token", `<h1>Invalid Token</h1><div class="alert alert-error">Token not found.</div>`));
    return;
  }

  if (row.used === 1) {
    addDebug(
      res,
      "Step 3: Token already used!",
      `This token was already consumed. Magic links are single-use.\n` +
        `Row: id=${row.id}, used=1`,
      "error"
    );
    res.setHeader("content-type", "text/html");
    res.status(401).send(
      html("Link Already Used", `
        <h1>Link Already Used</h1>
        <div class="alert alert-error">This magic link has already been used. Each link works only once.</div>
        <a href="/auth/magic/request" class="btn">Request New Link</a>
      `)
    );
    return;
  }

  // Mark as used
  db.prepare("UPDATE magic_tokens SET used = 1 WHERE id = ?").run(row.id);

  addDebug(
    res,
    "Step 3: Token marked as used",
    `UPDATE magic_tokens SET used = 1 WHERE id = '${row.id}'\n` +
      `This token can never be reused.`,
    "success"
  );

  // Create session
  req.session.email = decoded.email;
  req.session.authMethod = "magic";

  addDebug(
    res,
    "Step 4: Session created",
    `Session ID: ${req.sessionID}\nemail: ${decoded.email}\nauthMethod: magic`,
    "success"
  );

  res.redirect("/auth/magic/profile");
}

// ── GET /auth/magic/profile ──

export function showSuccess(req: Request, res: Response): void {
  if (!req.session.email || req.session.authMethod !== "magic") {
    res.redirect("/auth/magic/request");
    return;
  }

  addDebug(
    res,
    "Session loaded",
    `email: ${req.session.email}\nauthMethod: ${req.session.authMethod}`,
    "success"
  );

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Magic Link — Authenticated",
      `
    <h1>Magic Link — Authenticated</h1>
    <div class="alert alert-success">You logged in via magic link. No password was used.</div>

    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Email</td><td>${req.session.email}</td></tr>
      <tr><td>Auth Method</td><td>${req.session.authMethod}</td></tr>
      <tr><td>Session ID</td><td><code>${req.sessionID}</code></td></tr>
    </table>
    `
    )
  );
}
