import type { Request, Response, NextFunction } from "express";

export function requestLogger(req: Request, res: Response, next: NextFunction): void {
  const start = Date.now();

  res.on("finish", () => {
    const elapsed = Date.now() - start;
    const log = {
      method: req.method,
      url: req.originalUrl,
      status: res.statusCode,
      elapsed: `${elapsed}ms`,
      contentType: res.getHeader("content-type"),
    };
    console.log(`${log.method} ${log.url} → ${log.status} (${log.elapsed})`);
  });

  next();
}
