// ── Client-side debug panel enhancements ──
// 1. Collapsible toggle (handled by inline onclick in the panel HTML)
// 2. Fetch interceptor — captures AJAX calls and displays them
// 3. JWT decoder — decodes base64url tokens for display

(function () {
  "use strict";

  // ── Fetch interceptor ──
  // Wraps window.fetch to log requests/responses in the debug panel

  const originalFetch = window.fetch;

  window.fetch = async function (...args) {
    const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "unknown";
    const method = args[1]?.method || "GET";
    const start = performance.now();

    try {
      const response = await originalFetch.apply(this, args);
      const elapsed = Math.round(performance.now() - start);

      addFetchEntry(method, url, response.status, elapsed, response.headers);

      return response;
    } catch (err) {
      const elapsed = Math.round(performance.now() - start);
      addFetchEntry(method, url, "ERR", elapsed, null, err.message);
      throw err;
    }
  };

  function addFetchEntry(method, url, status, elapsed, headers, error) {
    const panel = document.querySelector(".debug-content");
    if (!panel) return;

    const entry = document.createElement("div");
    entry.className = `debug-entry debug-${error ? "error" : status < 400 ? "success" : "warning"}`;

    let headerText = "";
    if (headers) {
      const h = {};
      headers.forEach((value, key) => {
        h[key] = value;
      });
      headerText = JSON.stringify(h, null, 2);
    }

    entry.innerHTML = `
      <strong>fetch ${method} ${escapeHtml(url)}</strong>
      <pre>${status} (${elapsed}ms)${error ? "\n" + escapeHtml(error) : ""}${
        headerText ? "\n" + escapeHtml(headerText) : ""
      }</pre>
    `;

    panel.appendChild(entry);
  }

  // ── JWT decoder utility ──
  // Exposed globally so HTML pages can call decodeJwt(token)

  window.decodeJwt = function (token) {
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return { error: "Not a valid JWT (expected 3 parts)" };

      return {
        header: JSON.parse(atob(parts[0].replace(/-/g, "+").replace(/_/g, "/"))),
        payload: JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))),
        signature: parts[2],
      };
    } catch (e) {
      return { error: "Failed to decode JWT: " + e.message };
    }
  };

  // ── Helper to render decoded JWT into a container ──

  window.renderDecodedJwt = function (containerId, token) {
    const container = document.getElementById(containerId);
    if (!container || !token) return;

    const decoded = window.decodeJwt(token);

    if (decoded.error) {
      container.innerHTML = `<pre class="alert alert-error">${escapeHtml(decoded.error)}</pre>`;
      return;
    }

    container.innerHTML = `
      <div class="token-display">
        <h4>Header</h4>
        <pre>${escapeHtml(JSON.stringify(decoded.header, null, 2))}</pre>
      </div>
      <div class="token-display">
        <h4>Payload</h4>
        <pre>${escapeHtml(JSON.stringify(decoded.payload, null, 2))}</pre>
      </div>
      <div class="token-display">
        <h4>Signature (base64url)</h4>
        <pre>${escapeHtml(decoded.signature)}</pre>
      </div>
    `;
  };

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
