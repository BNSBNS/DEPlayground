import type { Request, Response } from "express";
import crypto from "node:crypto";
import { v4 as uuidv4 } from "uuid";
import db from "../../db.js";
import redis from "../../redis.js";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── GET /auth/apikey/generate ──

export function showGeneratePage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Generate API Key",
      `
    <h1>API Key Authentication</h1>
    <p>Generate an API key. The plaintext key is shown <strong>once</strong> — only the SHA-256 hash is stored in the database.</p>

    <form method="POST" action="/auth/apikey/generate">
      <div class="form-group">
        <label for="user_id">User ID (owner)</label>
        <input type="text" id="user_id" name="user_id" value="alice-001" required>
      </div>
      <div class="form-group">
        <label for="permissions">Permissions</label>
        <input type="text" id="permissions" name="permissions" value="read,write" required>
      </div>
      <button type="submit">Generate Key</button>
    </form>
    `
    )
  );
}

// ── POST /auth/apikey/generate ──
// 1. Generate 32 random bytes → hex string with ak_ prefix
// 2. SHA-256 hash the key
// 3. Store ONLY the hash in SQLite
// 4. Return the plaintext key ONCE

export function handleGenerate(req: Request, res: Response): void {
  const { user_id, permissions } = req.body as { user_id: string; permissions: string };

  // Generate random key
  const rawBytes = crypto.randomBytes(32);
  const plaintextKey = `ak_${rawBytes.toString("hex")}`;

  addDebug(
    res,
    "Step 1: Generate random bytes",
    `crypto.randomBytes(32) → ${rawBytes.toString("hex")}\n` +
      `Prefixed with 'ak_' → ${plaintextKey}`,
    "code"
  );

  // SHA-256 hash the key
  const keyHash = crypto.createHash("sha256").update(plaintextKey).digest("hex");

  addDebug(
    res,
    "Step 2: SHA-256 hash",
    `SHA-256(${plaintextKey.slice(0, 20)}...) → ${keyHash}\n\n` +
      `Only this hash is stored in the database.\n` +
      `The plaintext key is shown once and never stored.`,
    "code"
  );

  // Store in SQLite
  const id = uuidv4();
  db.prepare("INSERT INTO api_keys (id, key_hash, user_id, permissions) VALUES (?, ?, ?, ?)").run(
    id,
    keyHash,
    user_id,
    permissions
  );

  addDebug(
    res,
    "Step 3: Stored in SQLite",
    `INSERT INTO api_keys (id, key_hash, user_id, permissions)\n` +
      `VALUES ('${id}', '${keyHash}', '${user_id}', '${permissions}')`,
    "success"
  );

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "API Key Generated",
      `
    <h1>API Key Generated</h1>
    <div class="alert alert-success">
      Copy this key now — it will <strong>never be shown again</strong>.
    </div>

    <div class="token-display">
      <h4>Your API Key (show once)</h4>
      <pre>${plaintextKey}</pre>
    </div>

    <div class="token-display">
      <h4>Stored Hash (SHA-256)</h4>
      <pre>${keyHash}</pre>
    </div>

    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Key ID</td><td>${id}</td></tr>
      <tr><td>Owner</td><td>${user_id}</td></tr>
      <tr><td>Permissions</td><td>${permissions}</td></tr>
    </table>

    <div style="margin-top:1rem">
      <a href="/auth/apikey/test" class="btn btn-blue">Test This Key</a>
    </div>
    `
    )
  );
}

// ── GET /auth/apikey/test ──

export function showTestPage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Test API Key",
      `
    <h1>Test API Key</h1>
    <p>Paste your API key below. It will be sent as an <code>X-API-Key</code> header.</p>

    <div class="form-group">
      <label for="apikey">API Key</label>
      <input type="text" id="apikey" placeholder="ak_..." style="font-size:0.8rem">
    </div>
    <button onclick="testKey()" class="btn btn-blue">Test Key</button>

    <div id="result" style="margin-top:1rem"></div>

    <script>
      async function testKey() {
        const key = document.getElementById('apikey').value;
        const result = document.getElementById('result');
        try {
          const resp = await fetch('/auth/apikey/protected', {
            headers: { 'X-API-Key': key }
          });
          const text = await resp.text();
          result.innerHTML = '<h3>Response (' + resp.status + '):</h3>' + text;
        } catch (err) {
          result.innerHTML = '<div class="alert alert-error">' + err.message + '</div>';
        }
      }
    </script>
    `
    )
  );
}

// ── GET /auth/apikey/protected ──
// 1. Read X-API-Key header
// 2. SHA-256 hash the provided key
// 3. Look up hash in SQLite
// 4. Check rate limit in Redis (sliding window)

export async function handleProtected(req: Request, res: Response): Promise<void> {
  const apiKey = req.headers["x-api-key"] as string | undefined;

  addDebug(res, "Step 1: X-API-Key header", apiKey || "(missing)", apiKey ? "info" : "error");

  if (!apiKey) {
    res.status(401).json({ error: "Missing X-API-Key header" });
    return;
  }

  // Hash the provided key
  const keyHash = crypto.createHash("sha256").update(apiKey).digest("hex");

  addDebug(
    res,
    "Step 2: Hash provided key",
    `SHA-256(${apiKey.slice(0, 20)}...) → ${keyHash}\n` +
      `We hash the provided key and look up the hash — we never compare plaintext.`,
    "code"
  );

  // Look up in SQLite
  const row = db
    .prepare("SELECT id, user_id, permissions FROM api_keys WHERE key_hash = ?")
    .get(keyHash) as { id: string; user_id: string; permissions: string } | undefined;

  if (!row) {
    addDebug(res, "Step 3: Lookup", "No matching hash found in database.", "error");
    res.status(401).json({ error: "Invalid API key" });
    return;
  }

  addDebug(
    res,
    "Step 3: Key found",
    `Key ID: ${row.id}\nOwner: ${row.user_id}\nPermissions: ${row.permissions}`,
    "success"
  );

  // Rate limiting: sliding window in Redis
  const rateLimitKey = `apikey:rate:${row.id}`;
  const now = Date.now();
  const windowMs = 60_000; // 1 minute window
  const maxRequests = 10;

  // Remove entries outside the window
  await redis.zremrangebyscore(rateLimitKey, 0, now - windowMs);
  // Count remaining entries
  const requestCount = await redis.zcard(rateLimitKey);

  if (requestCount >= maxRequests) {
    addDebug(
      res,
      "Step 4: Rate limit exceeded",
      `${requestCount}/${maxRequests} requests in the last 60s.\n` +
        `Redis sorted set: ${rateLimitKey}`,
      "error"
    );
    res.status(429).json({ error: "Rate limit exceeded. Max 10 requests per minute." });
    return;
  }

  // Add this request
  await redis.zadd(rateLimitKey, now, `${now}`);
  await redis.expire(rateLimitKey, 60);

  addDebug(
    res,
    "Step 4: Rate limit check",
    `${requestCount + 1}/${maxRequests} requests in the last 60s.\n` +
      `Using Redis sorted set (ZRANGEBYSCORE) for sliding window.\n` +
      `Key: ${rateLimitKey}`,
    "success"
  );

  res.setHeader("content-type", "text/html");
  res.send(`
    <div class="alert alert-success">API key authenticated.</div>
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Key ID</td><td>${row.id}</td></tr>
      <tr><td>Owner</td><td>${row.user_id}</td></tr>
      <tr><td>Permissions</td><td>${row.permissions}</td></tr>
      <tr><td>Rate Limit</td><td>${requestCount + 1}/${maxRequests} per minute</td></tr>
    </table>
  `);
}
