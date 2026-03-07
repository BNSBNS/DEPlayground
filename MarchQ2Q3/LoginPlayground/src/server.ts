import "dotenv/config";
import express from "express";
import cookieParser from "cookie-parser";
import session from "express-session";
import RedisStore from "connect-redis";
import { createClient } from "redis";
import https from "node:https";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { requestLogger } from "./middleware/request-logger.js";
import { debugPanelMiddleware } from "./middleware/debug-panel.js";
import { html } from "./views/render.js";
import { seed } from "./db.js";

// Auth route modules
import { sessionRoutes } from "./auth/session/routes.js";
import { jwtRoutes } from "./auth/jwt/routes.js";
import { apikeyRoutes } from "./auth/apikey/routes.js";
import { magicRoutes } from "./auth/magic/routes.js";
import { oidcRoutes } from "./auth/oidc/routes.js";
import { entraRoutes } from "./auth/entra/routes.js";
import { samlRoutes } from "./auth/saml/routes.js";
import { mtlsRoutes } from "./auth/mtls/routes.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = parseInt(process.env.PORT || "3000", 10);
const MTLS_PORT = parseInt(process.env.MTLS_PORT || "3443", 10);

const app = express();

// ── Middleware ──
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());
app.use(requestLogger);
app.use("/static", express.static(path.join(__dirname, "static")));

// ── Redis session store ──
// connect-redis v7 requires the `redis` (node-redis) package, not ioredis.
// ioredis is used separately for direct Redis ops (JWT blacklist, rate limiting).
const redisClient = createClient({ url: process.env.REDIS_URL || "redis://localhost:6379" });
redisClient.connect().catch((err) => console.error("Redis session client error:", err));

app.use(
  session({
    store: new RedisStore({ client: redisClient }),
    secret: process.env.SESSION_SECRET || "dev-secret",
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: false, // set true in production with HTTPS
      maxAge: 1000 * 60 * 30, // 30 minutes
    },
  })
);

// Debug panel — inject into every HTML response
app.use(debugPanelMiddleware);

// ── Landing page ──
app.get("/", (_req, res) => {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Home",
      `
    <h1>Auth Methods Lab</h1>
    <p>Click any method below to walk through the full authentication flow. Open the debug panel at the bottom of every page to inspect headers, cookies, tokens, and every step of the flow.</p>

    <div class="card-grid">
      <a href="/auth/session/login" class="card">
        <h3>1. Session</h3>
        <p>Username + password, bcrypt, Redis sessions, HttpOnly cookies</p>
      </a>

      <a href="/auth/jwt/login" class="card">
        <h3>2. JWT</h3>
        <p>RS256 access tokens, HS256 refresh tokens, token rotation</p>
      </a>

      <a href="/auth/apikey/generate" class="card">
        <h3>3. API Key</h3>
        <p>SHA-256 hashed keys, X-API-Key header, rate limiting</p>
      </a>

      <a href="/auth/magic/request" class="card">
        <h3>4. Magic Link</h3>
        <p>Passwordless email, signed URLs, single-use tokens</p>
      </a>

      <a href="/auth/oidc/login" class="card">
        <h3>5. OIDC</h3>
        <p>OAuth 2.0 Authorization Code + PKCE, Keycloak IdP</p>
      </a>

      <a href="/auth/entra/login" class="card">
        <h3>6. Entra ID</h3>
        <p>Microsoft Entra simulation, groups/roles/tenant claims</p>
      </a>

      <a href="/auth/saml/login" class="card">
        <h3>7. SAML 2.0</h3>
        <p>AuthnRequest, XML signatures, assertion parsing</p>
      </a>

      <a href="/auth/mtls/test" class="card">
        <h3>8. mTLS</h3>
        <p>Mutual TLS, client certificates, CA trust chains</p>
      </a>
    </div>
    `
    )
  );
});

// ── Mount auth routes ──
app.use("/auth/session", sessionRoutes);
app.use("/auth/jwt", jwtRoutes);
app.use("/auth/apikey", apikeyRoutes);
app.use("/auth/magic", magicRoutes);
app.use("/auth/oidc", oidcRoutes);
app.use("/auth/entra", entraRoutes);
app.use("/auth/saml", samlRoutes);
app.use("/auth/mtls", mtlsRoutes);

// ── Start HTTP server ──
async function start(): Promise<void> {
  // Seed database with default users
  await seed();

  app.listen(PORT, () => {
    console.log(`Auth Methods Lab running at http://localhost:${PORT}`);
  });

  // ── Start mTLS HTTPS server (if certs exist) ──
  const caPath = process.env.MTLS_CA_PATH || "./shared/certs/ca.pem";
  const certPath = process.env.MTLS_SERVER_CERT_PATH || "./shared/certs/server.pem";
  const keyPath = process.env.MTLS_SERVER_KEY_PATH || "./shared/certs/server-key.pem";

  if (fs.existsSync(caPath) && fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    const mtlsApp = express();
    mtlsApp.use(express.json());
    mtlsApp.use(cookieParser());
    mtlsApp.use(requestLogger);
    mtlsApp.use(debugPanelMiddleware);
    mtlsApp.use("/auth/mtls", mtlsRoutes);

    const httpsServer = https.createServer(
      {
        ca: fs.readFileSync(caPath),
        cert: fs.readFileSync(certPath),
        key: fs.readFileSync(keyPath),
        requestCert: true,
        rejectUnauthorized: true,
      },
      mtlsApp
    );

    httpsServer.listen(MTLS_PORT, () => {
      console.log(`mTLS server running at https://localhost:${MTLS_PORT}`);
    });
  } else {
    console.log(
      `mTLS certs not found — run 'bash scripts/generate-certs.sh' to enable mTLS on port ${MTLS_PORT}`
    );
  }
}

start().catch(console.error);
