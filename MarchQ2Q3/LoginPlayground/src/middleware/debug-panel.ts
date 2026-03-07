import type { Request, Response, NextFunction } from "express";

// ── Types ──

export interface DebugEntry {
  label: string;
  detail: string;
  type?: "info" | "success" | "warning" | "error" | "code";
}

export interface DebugContext {
  entries: DebugEntry[];
  request: {
    method: string;
    url: string;
    headers: Record<string, string | string[] | undefined>;
    cookies: Record<string, string>;
    body?: unknown;
  };
  startTime: number;
}

// ── Middleware ──
// Attaches a DebugContext to res.locals and wraps res.send() to inject the panel.

export function debugPanelMiddleware(req: Request, res: Response, next: NextFunction): void {
  const debug: DebugContext = {
    entries: [],
    request: {
      method: req.method,
      url: req.originalUrl,
      headers: req.headers as Record<string, string | string[] | undefined>,
      cookies: req.cookies || {},
      body: req.body,
    },
    startTime: Date.now(),
  };

  res.locals.debug = debug;

  // Wrap res.send to inject debug panel into HTML responses
  const originalSend = res.send.bind(res);
  res.send = function (body: unknown): Response {
    if (
      typeof body === "string" &&
      body.includes("</body>") &&
      res.getHeader("content-type")?.toString().includes("text/html")
    ) {
      const panelHtml = renderDebugPanel(debug, res);
      body = body.replace("</body>", `${panelHtml}</body>`);
    }
    return originalSend(body);
  };

  next();
}

// ── Helper: add a debug entry from any handler ──

export function addDebug(res: Response, label: string, detail: string, type: DebugEntry["type"] = "info"): void {
  const debug = res.locals.debug as DebugContext | undefined;
  if (debug) {
    debug.entries.push({ label, detail, type });
  }
}

// ── Render the debug panel HTML ──

function renderDebugPanel(debug: DebugContext, res: Response): string {
  const elapsed = Date.now() - debug.startTime;

  const responseHeaders: Record<string, string> = {};
  const headerNames = res.getHeaderNames();
  for (const name of headerNames) {
    responseHeaders[name] = String(res.getHeader(name));
  }

  const entriesHtml = debug.entries
    .map(
      (e) => `
      <div class="debug-entry debug-${e.type || "info"}">
        <strong>${escapeHtml(e.label)}:</strong>
        <pre>${escapeHtml(e.detail)}</pre>
      </div>`
    )
    .join("");

  return `
  <div id="debug-panel" class="debug-panel">
    <button onclick="document.getElementById('debug-panel').classList.toggle('debug-open')" class="debug-toggle">
      Debug Panel (${elapsed}ms)
    </button>
    <div class="debug-content">
      <h3>Request</h3>
      <pre>${escapeHtml(debug.request.method)} ${escapeHtml(debug.request.url)}</pre>
      <details>
        <summary>Request Headers</summary>
        <pre>${escapeHtml(JSON.stringify(debug.request.headers, null, 2))}</pre>
      </details>
      <details>
        <summary>Cookies</summary>
        <pre>${escapeHtml(JSON.stringify(debug.request.cookies, null, 2))}</pre>
      </details>
      ${
        debug.request.body && Object.keys(debug.request.body as object).length > 0
          ? `<details>
              <summary>Request Body</summary>
              <pre>${escapeHtml(JSON.stringify(debug.request.body, null, 2))}</pre>
            </details>`
          : ""
      }

      <h3>Response</h3>
      <pre>Status: ${res.statusCode}</pre>
      <details>
        <summary>Response Headers</summary>
        <pre>${escapeHtml(JSON.stringify(responseHeaders, null, 2))}</pre>
      </details>

      <h3>Auth Flow Steps</h3>
      ${entriesHtml || "<p><em>No debug entries recorded for this request.</em></p>"}
    </div>
  </div>`;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
