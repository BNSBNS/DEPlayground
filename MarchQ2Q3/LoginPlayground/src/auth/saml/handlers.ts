import type { Request, Response } from "express";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { parseStringPromise } from "xml2js";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── Config ──

const SAML_IDP_SSO_URL = process.env.SAML_IDP_SSO_URL || "http://localhost:8080/realms/saml/protocol/saml";
const SAML_SP_ENTITY_ID = process.env.SAML_SP_ENTITY_ID || "auth-methods-lab";
const SAML_ACS_URL = process.env.SAML_ACS_URL || "http://localhost:3000/auth/saml/acs";

// Session types are in src/types/session.d.ts

// ── GET /auth/saml/login ──
// 1. Build an AuthnRequest XML document
// 2. Deflate + Base64 encode it
// 3. Redirect to Keycloak's SSO endpoint with SAMLRequest + RelayState

export function handleLogin(req: Request, res: Response): void {
  const requestId = `_${crypto.randomUUID()}`;
  const issueInstant = new Date().toISOString();
  const relayState = crypto.randomBytes(16).toString("hex");

  // Build the AuthnRequest XML
  const authnRequest = `<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
  xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
  xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
  ID="${requestId}"
  Version="2.0"
  IssueInstant="${issueInstant}"
  Destination="${SAML_IDP_SSO_URL}"
  AssertionConsumerServiceURL="${SAML_ACS_URL}"
  ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
  <saml:Issuer>${SAML_SP_ENTITY_ID}</saml:Issuer>
  <samlp:NameIDPolicy
    Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"
    AllowCreate="true"/>
</samlp:AuthnRequest>`;

  addDebug(
    res,
    "Step 1: AuthnRequest XML built",
    `${authnRequest}\n\n` +
      `Key fields:\n` +
      `  ID: ${requestId} (unique request identifier)\n` +
      `  Issuer: ${SAML_SP_ENTITY_ID} (our Service Provider entity ID)\n` +
      `  AssertionConsumerServiceURL: ${SAML_ACS_URL} (where IdP POSTs back)\n` +
      `  ProtocolBinding: HTTP-POST (IdP will POST the response)`,
    "code"
  );

  // Deflate + Base64 encode for HTTP-Redirect binding
  const deflated = zlib.deflateRawSync(Buffer.from(authnRequest, "utf-8"));
  const encoded = deflated.toString("base64");

  addDebug(
    res,
    "Step 2: Encode for redirect",
    `1. Deflate (raw) the XML → ${deflated.length} bytes\n` +
      `2. Base64 encode → ${encoded.length} chars\n` +
      `3. URL-encode for query parameter\n\n` +
      `This is the HTTP-Redirect binding: the AuthnRequest goes in the URL.`,
    "code"
  );

  // Store relay state in session for verification
  req.session.samlRelayState = relayState;

  addDebug(
    res,
    "Step 3: RelayState",
    `RelayState: ${relayState}\n` +
      `Stored in session. The IdP echoes it back in the response.\n` +
      `Used to correlate the response with this specific request.`,
    "info"
  );

  // Build redirect URL
  const params = new URLSearchParams({
    SAMLRequest: encoded,
    RelayState: relayState,
  });

  const ssoUrl = `${SAML_IDP_SSO_URL}?${params}`;

  addDebug(
    res,
    "Step 4: Redirect to SAML IdP",
    `URL: ${ssoUrl.slice(0, 200)}...\n\n` +
      `The browser is redirected to Keycloak's SAML SSO endpoint.\n` +
      `After login, Keycloak POSTs a SAMLResponse to our ACS URL.`,
    "info"
  );

  res.redirect(ssoUrl);
}

// ── POST /auth/saml/acs ──
// Assertion Consumer Service: receives the SAMLResponse from the IdP.
// 1. Base64 decode the SAMLResponse
// 2. Parse the XML
// 3. (Simplified) Extract NameID and attributes from the assertion
// 4. Create session

export async function handleAcs(req: Request, res: Response): Promise<void> {
  const { SAMLResponse, RelayState } = req.body as { SAMLResponse: string; RelayState: string };

  if (!SAMLResponse) {
    res.setHeader("content-type", "text/html");
    res.status(400).send(html("SAML Error", `<div class="alert alert-error">Missing SAMLResponse.</div>`));
    return;
  }

  addDebug(
    res,
    "Step 1: SAMLResponse received (POST)",
    `SAMLResponse (base64, first 100 chars): ${SAMLResponse.slice(0, 100)}...\n` +
      `RelayState: ${RelayState}`,
    "info"
  );

  // Verify RelayState
  if (RelayState !== req.session.samlRelayState) {
    addDebug(
      res,
      "Step 2: RelayState mismatch",
      `Expected: ${req.session.samlRelayState}\nGot: ${RelayState}`,
      "warning"
    );
    // In production this should be an error, but Keycloak may not always echo it back perfectly
  } else {
    addDebug(res, "Step 2: RelayState verified", "Matches session.", "success");
  }

  // Base64 decode the SAMLResponse
  const xmlBuffer = Buffer.from(SAMLResponse, "base64");
  const xmlString = xmlBuffer.toString("utf-8");

  addDebug(
    res,
    "Step 3: Decoded SAMLResponse XML",
    `${xmlString.slice(0, 2000)}${xmlString.length > 2000 ? "\n...(truncated)" : ""}`,
    "code"
  );

  // Parse XML
  let parsed: Record<string, unknown>;
  try {
    parsed = await parseStringPromise(xmlString, {
      tagNameProcessors: [(name: string) => name.replace(/.*:/, "")], // strip namespace prefix
      explicitArray: false,
    });
  } catch (err) {
    addDebug(res, "Step 4: XML parse failed", (err as Error).message, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("SAML Error", `<div class="alert alert-error">Failed to parse SAMLResponse XML.</div>`));
    return;
  }

  addDebug(
    res,
    "Step 4: XML parsed",
    JSON.stringify(parsed, null, 2).slice(0, 3000),
    "success"
  );

  // Extract assertion data (navigate the XML structure)
  // The structure is: Response > Assertion > Subject > NameID, AttributeStatement > Attribute
  try {
    const response = (parsed as Record<string, Record<string, unknown>>).Response || parsed;
    const assertion =
      (response as Record<string, unknown>).Assertion ||
      (response as Record<string, Record<string, unknown>>).EncryptedAssertion;

    if (!assertion) {
      addDebug(res, "Step 5: No assertion found", "The response may use encrypted assertions.", "warning");
    }

    // Extract NameID
    const subject = (assertion as Record<string, Record<string, unknown>>)?.Subject;
    const nameId = subject?.NameID;
    const nameIdValue = typeof nameId === "string" ? nameId : (nameId as Record<string, string>)?._ || "unknown";

    addDebug(
      res,
      "Step 5: NameID extracted",
      `NameID: ${nameIdValue}\n\n` +
        `The NameID is the primary identifier from the IdP.\n` +
        `Format depends on IdP config (email, persistent, transient).`,
      "success"
    );

    // Extract attributes
    const attrStatement = (assertion as Record<string, Record<string, unknown>>)?.AttributeStatement;
    const attributes: Record<string, string> = {};

    if (attrStatement) {
      let attrs = (attrStatement as Record<string, unknown>).Attribute;
      if (!Array.isArray(attrs)) attrs = attrs ? [attrs] : [];

      for (const attr of attrs as Array<Record<string, unknown>>) {
        const name = (attr.$ as Record<string, string>)?.Name || (attr as Record<string, string>).Name || "unknown";
        const value = attr.AttributeValue;
        attributes[name] = typeof value === "string" ? value : (value as Record<string, string>)?._ || JSON.stringify(value);
      }
    }

    addDebug(
      res,
      "Step 6: Attributes extracted",
      JSON.stringify(attributes, null, 2) || "(no attributes)",
      "success"
    );

    addDebug(
      res,
      "Step 7: Signature verification (simplified)",
      `In production, you MUST verify the XML digital signature:\n` +
        `1. Extract the <Signature> element from the assertion\n` +
        `2. Fetch the IdP's X.509 certificate from metadata\n` +
        `3. Verify the signature covers the assertion content\n` +
        `4. Check conditions: NotBefore, NotOnOrAfter, Audience\n\n` +
        `This lab skips signature verification for readability.\n` +
        `In production, use a library like 'saml2-js' or 'passport-saml'.`,
      "warning"
    );

    // Create session
    req.session.samlNameId = nameIdValue;
    req.session.samlAttributes = attributes;
    req.session.samlRawAssertion = xmlString;
    req.session.email = attributes.email || nameIdValue;
    req.session.authMethod = "saml";

    addDebug(res, "Step 8: Session created", `NameID: ${nameIdValue}\nAttributes: ${JSON.stringify(attributes)}`, "success");

    delete req.session.samlRelayState;

    res.redirect("/auth/saml/profile");
  } catch (err) {
    addDebug(res, "Step 5: Assertion extraction failed", (err as Error).message, "error");
    res.setHeader("content-type", "text/html");
    res.send(html("SAML Error", `<div class="alert alert-error">Failed to extract assertion: ${(err as Error).message}</div>`));
  }
}

// ── GET /auth/saml/profile ──

export function showProfile(req: Request, res: Response): void {
  if (!req.session.samlNameId) {
    res.redirect("/auth/saml/login");
    return;
  }

  const attributes = req.session.samlAttributes || {};
  const attrRows = Object.entries(attributes)
    .map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`)
    .join("");

  addDebug(res, "Session loaded", `NameID: ${req.session.samlNameId}\nAttributes: ${JSON.stringify(attributes)}`, "success");

  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "SAML Profile",
      `
    <h1>SAML 2.0 — Profile</h1>
    <div class="alert alert-success">Authenticated via SAML 2.0 (Keycloak IdP).</div>

    <h2>Identity</h2>
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>NameID</td><td>${req.session.samlNameId}</td></tr>
      <tr><td>Auth Method</td><td>saml</td></tr>
      <tr><td>Session ID</td><td><code>${req.sessionID}</code></td></tr>
    </table>

    ${
      attrRows
        ? `<h2>SAML Attributes</h2>
           <table><tr><th>Attribute</th><th>Value</th></tr>${attrRows}</table>`
        : ""
    }

    <h2>Raw SAMLResponse XML</h2>
    <details>
      <summary>Click to expand (large)</summary>
      <pre style="font-size:0.65rem;max-height:400px;overflow:auto">${escapeHtml(req.session.samlRawAssertion || "")}</pre>
    </details>
    `
    )
  );
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
