import type { Request, Response } from "express";
import crypto from "node:crypto";
import * as jose from "jose";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── Config ──
// Same OIDC protocol, but pointing to the "entra" realm that mimics Microsoft Entra ID.

const ISSUER = process.env.ENTRA_ISSUER || "http://localhost:8080/realms/entra";
const CLIENT_ID = process.env.ENTRA_CLIENT_ID || "auth-lab-entra";
const CLIENT_SECRET = process.env.ENTRA_CLIENT_SECRET || "auth-lab-entra-secret";
const REDIRECT_URI = `http://localhost:${process.env.PORT || "3000"}/auth/entra/callback`;

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

function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString("base64url");
}

function generateCodeChallenge(verifier: string): string {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

// Session types are in src/types/session.d.ts

// ── GET /auth/entra/login ──
// Same OIDC Authorization Code + PKCE flow, but against the "entra" realm.

export async function handleLogin(req: Request, res: Response): Promise<void> {
  let config;
  try {
    config = await getOidcConfig();
  } catch (err) {
    addDebug(res, "Entra Discovery failed", `Could not reach ${ISSUER}\n${(err as Error).message}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(
      html("Entra Error", `
        <h1>Entra ID Discovery Failed</h1>
        <div class="alert alert-error">Could not reach Keycloak at ${ISSUER}. Make sure <code>docker compose up -d</code> is running.</div>
      `)
    );
    return;
  }

  addDebug(
    res,
    "Step 1: Entra OIDC Discovery",
    `Fetched: ${ISSUER}/.well-known/openid-configuration\n` +
      `This is identical to standard OIDC — Entra ID uses the same protocol.\n\n` +
      `authorization_endpoint: ${config.authorization_endpoint}\n` +
      `token_endpoint: ${config.token_endpoint}`,
    "info"
  );

  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);
  const state = crypto.randomBytes(16).toString("hex");

  req.session.entraState = state;
  req.session.entraCodeVerifier = codeVerifier;

  addDebug(res, "Step 2: PKCE + State", `verifier: ${codeVerifier}\nchallenge: ${codeChallenge}\nstate: ${state}`, "code");

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

  addDebug(res, "Step 3: Redirect to Entra IdP", authorizeUrl, "info");

  res.redirect(authorizeUrl);
}

// ── GET /auth/entra/callback?code=...&state=... ──

export async function handleCallback(req: Request, res: Response): Promise<void> {
  const { code, state, error, error_description } = req.query as Record<string, string>;

  if (error) {
    addDebug(res, "Callback error", `${error}: ${error_description}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("Entra Error", `<h1>Entra Error</h1><div class="alert alert-error">${error}: ${error_description}</div>`));
    return;
  }

  addDebug(res, "Step 1: Callback received", `code: ${code}\nstate: ${state}`, "info");

  if (state !== req.session.entraState) {
    addDebug(res, "Step 2: State mismatch", `Expected: ${req.session.entraState}\nGot: ${state}`, "error");
    res.setHeader("content-type", "text/html");
    res.status(403).send(html("State Mismatch", `<div class="alert alert-error">State mismatch.</div>`));
    return;
  }

  addDebug(res, "Step 2: State verified", "CSRF check passed.", "success");

  const config = await getOidcConfig();

  const tokenBody = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: REDIRECT_URI,
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    code_verifier: req.session.entraCodeVerifier || "",
  });

  const tokenResp = await fetch(config.token_endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: tokenBody,
  });

  const tokenData = (await tokenResp.json()) as {
    access_token?: string;
    id_token?: string;
    error?: string;
    error_description?: string;
  };

  if (tokenData.error) {
    addDebug(res, "Step 3: Token exchange failed", `${tokenData.error}: ${tokenData.error_description}`, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("Token Error", `<div class="alert alert-error">${tokenData.error}</div>`));
    return;
  }

  addDebug(res, "Step 3: Tokens received", `id_token: ${tokenData.id_token?.slice(0, 50)}...`, "success");

  // Verify ID token
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
    res.send(html("Token Error", `<div class="alert alert-error">${(err as Error).message}</div>`));
    return;
  }

  addDebug(
    res,
    "Step 4: ID token verified",
    `Claims:\n${JSON.stringify(claims, null, 2)}`,
    "success"
  );

  // ── Entra-specific: Parse groups, roles, tenant ID ──
  const groups = (claims.groups as string[]) || [];
  const roles = (claims.roles as string[]) || (claims.realm_access as { roles?: string[] })?.roles || [];
  const tenantId = (claims.tid as string) || claims.azp as string || "unknown";

  addDebug(
    res,
    "Step 5: Entra-specific claims",
    `groups: ${JSON.stringify(groups)}\n` +
      `roles: ${JSON.stringify(roles)}\n` +
      `tid (tenant ID): ${tenantId}\n\n` +
      `In real Entra ID, these claims come from Azure AD group memberships\n` +
      `and app role assignments configured in the Azure portal.\n\n` +
      `Authorization example:\n` +
      `  if (groups.includes("Engineering")) → allow access\n` +
      `  if (roles.includes("Admin")) → show admin panel`,
    "info"
  );

  // Demonstrate authorization decision
  const isEngineering = groups.includes("Engineering");
  const isAdmin = roles.includes("Admin") || roles.includes("admin");

  addDebug(
    res,
    "Step 6: Authorization decision",
    `Is in Engineering group? ${isEngineering}\n` +
      `Has Admin role? ${isAdmin}\n\n` +
      `This is how Entra ID enables role-based access control (RBAC).\n` +
      `Your code checks claims — it doesn't manage users directly.`,
    isEngineering || isAdmin ? "success" : "warning"
  );

  // Store in session
  req.session.entraIdToken = tokenData.id_token;
  req.session.entraClaims = claims as Record<string, unknown>;
  req.session.email = claims.email as string;
  req.session.authMethod = "entra";

  delete req.session.entraState;
  delete req.session.entraCodeVerifier;

  res.redirect("/auth/entra/profile");
}

// ── GET /auth/entra/profile ──

export function showProfile(req: Request, res: Response): void {
  if (!req.session.entraClaims) {
    res.redirect("/auth/entra/login");
    return;
  }

  const claims = req.session.entraClaims;
  const groups = (claims.groups as string[]) || [];
  const roles = (claims.roles as string[]) || (claims.realm_access as { roles?: string[] })?.roles || [];
  const tenantId = (claims.tid as string) || claims.azp as string || "—";

  const standardClaims = ["sub", "email", "name", "preferred_username", "iss", "aud", "iat", "exp"];
  const entraSpecificClaims = Object.keys(claims).filter((k) => !standardClaims.includes(k));

  addDebug(res, "Session loaded", JSON.stringify(claims, null, 2), "success");

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "Entra ID Profile",
      `
    <h1>Entra ID (Simulated) — Profile</h1>
    <div class="alert alert-success">Authenticated via Entra ID (OIDC with enterprise claims).</div>

    <h2>Identity</h2>
    <table>
      <tr><th>Claim</th><th>Value</th></tr>
      <tr><td>email</td><td>${claims.email || "—"}</td></tr>
      <tr><td>name</td><td>${claims.name || "—"}</td></tr>
      <tr><td>sub</td><td>${claims.sub}</td></tr>
      <tr><td>Tenant ID (tid)</td><td>${tenantId}</td></tr>
    </table>

    <h2>Groups & Roles (Entra-Specific)</h2>
    <table>
      <tr><th>Claim</th><th>Value</th></tr>
      <tr><td>groups</td><td><pre>${JSON.stringify(groups, null, 2)}</pre></td></tr>
      <tr><td>roles</td><td><pre>${JSON.stringify(roles, null, 2)}</pre></td></tr>
    </table>

    <h2>Authorization Check</h2>
    <div class="alert ${groups.includes("Engineering") ? "alert-success" : "alert-error"}">
      Engineering group: ${groups.includes("Engineering") ? "MEMBER" : "NOT A MEMBER"}
    </div>

    <h2>All Claims</h2>
    <table>
      <tr><th>Claim</th><th>Value</th><th>Standard?</th></tr>
      ${Object.entries(claims)
        .map(
          ([k, v]) =>
            `<tr><td>${k}</td><td><pre>${JSON.stringify(v, null, 2)}</pre></td><td>${
              standardClaims.includes(k) ? "OIDC Standard" : "Entra-Specific"
            }</td></tr>`
        )
        .join("")}
    </table>

    <h2>Raw ID Token</h2>
    <div id="entra-token-decoded"></div>
    <script>renderDecodedJwt('entra-token-decoded', '${req.session.entraIdToken}');</script>
    `
    )
  );
}
