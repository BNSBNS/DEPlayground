import type { Request, Response } from "express";
import crypto from "node:crypto";
import * as jose from "jose";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── Config ──

const ISSUER = process.env.OIDC_ISSUER || "http://localhost:8080/realms/oidc";
const CLIENT_ID = process.env.OIDC_CLIENT_ID || "auth-lab-oidc";
const CLIENT_SECRET = process.env.OIDC_CLIENT_SECRET || "auth-lab-oidc-secret";
const REDIRECT_URI = `http://localhost:${process.env.PORT || "3000"}/auth/oidc/callback`;

// ── OIDC Discovery ──
// Fetch the well-known config to get authorize/token/jwks endpoints.

async function getOidcConfig(): Promise<{
  authorization_endpoint: string;
  token_endpoint: string;
  jwks_uri: string;
  issuer: string;
}> {
  const resp = await fetch(`${ISSUER}/.well-known/openid-configuration`);
  return resp.json() as Promise<{
    authorization_endpoint: string;
    token_endpoint: string;
    jwks_uri: string;
    issuer: string;
  }>;
}

// ── PKCE helpers ──

function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString("base64url");
}

function generateCodeChallenge(verifier: string): string {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

// Session types are in src/types/session.d.ts

// ── GET /auth/oidc/login ──
// 1. Generate state (CSRF protection) and PKCE (code_verifier → code_challenge)
// 2. Store both in session
// 3. Redirect to Keycloak's /authorize endpoint

export async function handleLogin(req: Request, res: Response): Promise<void> {
  let config;
  try {
    config = await getOidcConfig();
  } catch (err) {
    addDebug(res, "OIDC Discovery failed", `Could not reach ${ISSUER}\n${(err as Error).message}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(
      html("OIDC Error", `
        <h1>OIDC Discovery Failed</h1>
        <div class="alert alert-error">Could not reach Keycloak at ${ISSUER}. Make sure <code>docker compose up -d</code> is running.</div>
      `)
    );
    return;
  }

  addDebug(
    res,
    "Step 1: OIDC Discovery",
    `Fetched: ${ISSUER}/.well-known/openid-configuration\n\n` +
      `authorization_endpoint: ${config.authorization_endpoint}\n` +
      `token_endpoint: ${config.token_endpoint}\n` +
      `jwks_uri: ${config.jwks_uri}`,
    "info"
  );

  // Generate PKCE pair
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);

  addDebug(
    res,
    "Step 2: PKCE generated",
    `code_verifier: ${codeVerifier}\n` +
      `code_challenge: ${codeChallenge}\n` +
      `method: S256 (SHA-256 of verifier, base64url encoded)\n\n` +
      `PKCE prevents authorization code interception attacks.\n` +
      `The verifier stays on the server; only the challenge goes to the IdP.`,
    "code"
  );

  // Generate state (CSRF protection)
  const state = crypto.randomBytes(16).toString("hex");

  addDebug(
    res,
    "Step 3: State generated",
    `state: ${state}\n\nStored in session. Verified on callback to prevent CSRF.`,
    "code"
  );

  // Store in session
  req.session.oidcState = state;
  req.session.oidcCodeVerifier = codeVerifier;

  // Build the /authorize URL
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: "openid profile email",
    state,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  const authorizeUrl = `${config.authorization_endpoint}?${params}`;

  addDebug(
    res,
    "Step 4: Redirect to IdP",
    `URL: ${authorizeUrl}\n\n` +
      `The browser redirects to Keycloak's login page.\n` +
      `After the user logs in, Keycloak redirects back to:\n` +
      `${REDIRECT_URI}?code=...&state=...`,
    "info"
  );

  res.redirect(authorizeUrl);
}

// ── GET /auth/oidc/callback?code=...&state=... ──
// 1. Verify state matches session
// 2. Exchange authorization code for tokens at the /token endpoint
// 3. Verify ID token signature via JWKS
// 4. Create session with decoded claims

export async function handleCallback(req: Request, res: Response): Promise<void> {
  const { code, state, error, error_description } = req.query as Record<string, string>;

  if (error) {
    addDebug(res, "Callback error from IdP", `${error}: ${error_description}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("OIDC Error", `<h1>OIDC Error</h1><div class="alert alert-error">${error}: ${error_description}</div>`));
    return;
  }

  addDebug(res, "Step 1: Callback received", `code: ${code}\nstate: ${state}`, "info");

  // Verify state
  if (state !== req.session.oidcState) {
    addDebug(
      res,
      "Step 2: State mismatch!",
      `Expected: ${req.session.oidcState}\nReceived: ${state}\n\nThis could be a CSRF attack.`,
      "error"
    );
    res.setHeader("content-type", "text/html");
    res.status(403).send(html("State Mismatch", `<h1>State Mismatch</h1><div class="alert alert-error">Possible CSRF attack. State doesn't match.</div>`));
    return;
  }

  addDebug(res, "Step 2: State verified", `State matches session. CSRF check passed.`, "success");

  // Get OIDC config for token endpoint
  const config = await getOidcConfig();

  // Exchange code for tokens
  const tokenBody = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: REDIRECT_URI,
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    code_verifier: req.session.oidcCodeVerifier || "",
  });

  addDebug(
    res,
    "Step 3: Token exchange",
    `POST ${config.token_endpoint}\n\n` +
      `Body:\n` +
      `  grant_type: authorization_code\n` +
      `  code: ${code}\n` +
      `  redirect_uri: ${REDIRECT_URI}\n` +
      `  client_id: ${CLIENT_ID}\n` +
      `  client_secret: ***\n` +
      `  code_verifier: ${req.session.oidcCodeVerifier}`,
    "code"
  );

  const tokenResp = await fetch(config.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: tokenBody,
  });

  const tokenData = (await tokenResp.json()) as {
    access_token?: string;
    id_token?: string;
    refresh_token?: string;
    token_type?: string;
    expires_in?: number;
    error?: string;
    error_description?: string;
  };

  if (tokenData.error) {
    addDebug(res, "Step 3: Token exchange failed", `${tokenData.error}: ${tokenData.error_description}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("Token Error", `<h1>Token Exchange Failed</h1><div class="alert alert-error">${tokenData.error}: ${tokenData.error_description}</div>`));
    return;
  }

  addDebug(
    res,
    "Step 3: Tokens received",
    `access_token: ${tokenData.access_token?.slice(0, 50)}...\n` +
      `id_token: ${tokenData.id_token?.slice(0, 50)}...\n` +
      `token_type: ${tokenData.token_type}\n` +
      `expires_in: ${tokenData.expires_in}s`,
    "success"
  );

  // Verify ID token signature via JWKS
  const JWKS = jose.createRemoteJWKSet(new URL(config.jwks_uri));

  let claims: jose.JWTPayload;
  try {
    const { payload } = await jose.jwtVerify(tokenData.id_token!, JWKS, {
      issuer: config.issuer,
      audience: CLIENT_ID,
    });
    claims = payload;
  } catch (err) {
    addDebug(res, "Step 4: ID token verification failed", (err as Error).message, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("Token Error", `<h1>ID Token Verification Failed</h1><div class="alert alert-error">${(err as Error).message}</div>`));
    return;
  }

  addDebug(
    res,
    "Step 4: ID token verified via JWKS",
    `JWKS URI: ${config.jwks_uri}\n` +
      `Issuer check: ${config.issuer} ✓\n` +
      `Audience check: ${CLIENT_ID} ✓\n` +
      `Signature: valid ✓\n\n` +
      `Decoded claims:\n${JSON.stringify(claims, null, 2)}`,
    "success"
  );

  // Store in session
  req.session.oidcIdToken = tokenData.id_token;
  req.session.oidcClaims = claims as Record<string, unknown>;
  req.session.email = claims.email as string;
  req.session.authMethod = "oidc";

  // Clean up PKCE/state from session
  delete req.session.oidcState;
  delete req.session.oidcCodeVerifier;

  res.redirect("/auth/oidc/profile");
}

// ── GET /auth/oidc/profile ──

export function showProfile(req: Request, res: Response): void {
  if (!req.session.oidcClaims) {
    res.redirect("/auth/oidc/login");
    return;
  }

  const claims = req.session.oidcClaims;

  addDebug(res, "Session loaded", `Claims from ID token:\n${JSON.stringify(claims, null, 2)}`, "success");

  const claimsRows = Object.entries(claims)
    .map(([key, value]) => `<tr><td>${key}</td><td><pre>${JSON.stringify(value, null, 2)}</pre></td></tr>`)
    .join("");

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "OIDC Profile",
      `
    <h1>OAuth 2.0 / OIDC — Profile</h1>
    <div class="alert alert-success">Authenticated via OpenID Connect (Keycloak).</div>

    <h2>ID Token Claims</h2>
    <table>
      <tr><th>Claim</th><th>Value</th></tr>
      ${claimsRows}
    </table>

    <h2>Raw ID Token</h2>
    <div class="token-display">
      <h4>JWT</h4>
      <pre style="font-size:0.7rem">${req.session.oidcIdToken}</pre>
    </div>
    <div id="id-token-decoded"></div>
    <script>renderDecodedJwt('id-token-decoded', '${req.session.oidcIdToken}');</script>
    `
    )
  );
}
