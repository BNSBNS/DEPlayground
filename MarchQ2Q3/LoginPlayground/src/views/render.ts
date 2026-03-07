// ── Template literal view renderer ──
// Every page is rendered through this function.
// No Handlebars, no templating engine — just a function that returns HTML.
// The junior can Ctrl+F into any handler and see exactly what HTML gets returned.

export function html(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} — Auth Methods Lab</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav class="nav">
    <a href="/" class="nav-brand">Auth Lab</a>
    <div class="nav-links">
      <a href="/auth/session/login">Session</a>
      <a href="/auth/jwt/login">JWT</a>
      <a href="/auth/apikey/generate">API Key</a>
      <a href="/auth/magic/request">Magic Link</a>
      <a href="/auth/oidc/login">OIDC</a>
      <a href="/auth/entra/login">Entra ID</a>
      <a href="/auth/saml/login">SAML</a>
      <a href="/auth/mtls/test">mTLS</a>
    </div>
  </nav>

  <main class="main">
    ${body}
  </main>

  <script src="/static/debug-panel.js"></script>
</body>
</html>`;
}
