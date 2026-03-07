import type { Request, Response } from "express";
import type { TLSSocket } from "node:tls";
import { html } from "../../views/render.js";
import { addDebug } from "../../middleware/debug-panel.js";

// ── GET /auth/mtls/test ──
// Shows instructions for testing mTLS with curl.
// This endpoint is served on the main HTTP server (:3000) for convenience.

export function showTestPage(_req: Request, res: Response): void {
  res.setHeader("content-type", "text/html");
  res.send(
    html(
      "mTLS Test",
      `
    <h1>Mutual TLS (mTLS)</h1>
    <p>mTLS authenticates at the <strong>transport layer</strong>. The client presents a certificate during the TLS handshake — before any HTTP request is sent.</p>

    <h2>How It Works</h2>
    <ol>
      <li>Server starts HTTPS with <code>requestCert: true</code> and a trusted CA</li>
      <li>During TLS handshake, the server requests the client's certificate</li>
      <li>Client presents <code>client.pem</code> (signed by the same CA)</li>
      <li>Server verifies the client cert was signed by the trusted CA</li>
      <li>Server extracts the CN (Common Name) from the certificate</li>
      <li>The HTTP request proceeds — identity is already established</li>
    </ol>

    <h2>Test with curl</h2>
    <p>Run this from the project root:</p>
    <pre>curl --cert shared/certs/client.pem \\
     --key shared/certs/client-key.pem \\
     --cacert shared/certs/ca.pem \\
     https://localhost:3443/auth/mtls/protected</pre>

    <h2>What Each File Does</h2>
    <table>
      <tr><th>File</th><th>Purpose</th></tr>
      <tr><td><code>ca.pem</code></td><td>Certificate Authority — both server and client trust this CA</td></tr>
      <tr><td><code>server.pem</code></td><td>Server's certificate (signed by CA) — proves server identity</td></tr>
      <tr><td><code>server-key.pem</code></td><td>Server's private key</td></tr>
      <tr><td><code>client.pem</code></td><td>Client's certificate (signed by CA) — proves client identity</td></tr>
      <tr><td><code>client-key.pem</code></td><td>Client's private key</td></tr>
    </table>

    <h2>Why You Can't Test This in the Browser</h2>
    <p>Browsers don't send client certificates by default. You'd need to:</p>
    <ol>
      <li>Import the CA cert into your browser's trust store</li>
      <li>Import the client cert + key as a PKCS12 (.p12) file</li>
      <li>The browser prompts you to select a certificate when the server requests one</li>
    </ol>
    <p>For this lab, curl is the simplest way to test.</p>

    <div class="alert alert-info" style="margin-top:1rem">
      <strong>Note:</strong> The mTLS server runs on port <strong>3443</strong> (HTTPS). Make sure you ran <code>bash scripts/generate-certs.sh</code> first.
    </div>
    `
    )
  );
}

// ── GET /auth/mtls/protected ──
// This runs on the mTLS HTTPS server (:3443).
// The TLS handshake has already verified the client cert by the time we get here.

export function handleProtected(req: Request, res: Response): void {
  const socket = req.socket as TLSSocket;

  // Check if we're on the mTLS server (HTTPS with client cert)
  if (!socket.getPeerCertificate || !socket.encrypted) {
    addDebug(
      res,
      "Not on mTLS server",
      "This endpoint must be accessed via https://localhost:3443\n" +
        "The main HTTP server on :3000 doesn't do client cert verification.",
      "error"
    );
    res.status(400).json({
      error: "This endpoint requires mTLS. Use https://localhost:3443/auth/mtls/protected",
    });
    return;
  }

  const cert = socket.getPeerCertificate();

  if (!cert || !cert.subject) {
    addDebug(res, "No client certificate", "TLS handshake completed but no client cert was presented.", "error");
    res.status(401).json({ error: "No client certificate" });
    return;
  }

  addDebug(
    res,
    "Step 1: TLS handshake complete",
    `The client certificate was verified during the TLS handshake.\n` +
      `By the time this handler runs, we already know the cert is valid.`,
    "success"
  );

  addDebug(
    res,
    "Step 2: Client certificate details",
    `Subject:\n${JSON.stringify(cert.subject, null, 2)}\n\n` +
      `Issuer:\n${JSON.stringify(cert.issuer, null, 2)}\n\n` +
      `Valid from: ${cert.valid_from}\n` +
      `Valid to: ${cert.valid_to}\n` +
      `Serial: ${cert.serialNumber}\n` +
      `Fingerprint: ${cert.fingerprint}`,
    "code"
  );

  const cn = cert.subject.CN || "unknown";

  addDebug(
    res,
    "Step 3: Identity extracted",
    `Common Name (CN): ${cn}\n\n` +
      `In mTLS, the CN is typically the client's identity.\n` +
      `The CA vouches for this identity by signing the certificate.`,
    "success"
  );

  res.json({
    authenticated: true,
    method: "mTLS",
    identity: cn,
    certificate: {
      subject: cert.subject,
      issuer: cert.issuer,
      validFrom: cert.valid_from,
      validTo: cert.valid_to,
      serialNumber: cert.serialNumber,
      fingerprint: cert.fingerprint,
    },
  });
}
