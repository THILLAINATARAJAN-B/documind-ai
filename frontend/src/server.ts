import {
  AngularNodeAppEngine,
  createNodeRequestHandler,
  isMainModule,
  writeResponseToNodeResponse,
} from '@angular/ssr/node';
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { join } from 'node:path';

const browserDistFolder = join(import.meta.dirname, '../browser');

// SSR calls backend via Docker internal network name, not localhost
// Browser calls use environment.apiUrl = '' (relative) or localhost:8001
const BACKEND_INTERNAL_URL =
  process.env['BACKEND_URL'] || 'http://backend:8000';

const app = express();
const angularApp = new AngularNodeAppEngine();

// ── API Proxy ────────────────────────────────────────────────────────────────
// All /auth/*, /upload/*, /chat/* requests from SSR are proxied to the
// backend Docker service using its internal network name.
// This fixes SSR CORS: the SSR server talks to backend:8000 (internal),
// not localhost:8001 (which doesn't exist inside Docker).
app.use(
  ['/auth', '/upload', '/chat', '/health'],
  createProxyMiddleware({
    target: BACKEND_INTERNAL_URL,
    changeOrigin: true,
    on: {
      error: (err, req, res: any) => {
        console.error('[SSR Proxy] Error:', err.message);
        res.status(502).json({ detail: 'Backend unavailable' });
      },
    },
  })
);

// ── Static files ─────────────────────────────────────────────────────────────
app.use(
  express.static(browserDistFolder, {
    maxAge: '1y',
    index: false,
    redirect: false,
  })
);

// ── Angular SSR ───────────────────────────────────────────────────────────────
app.use((req, res, next) => {
  angularApp
    .handle(req)
    .then((response) =>
      response ? writeResponseToNodeResponse(response, res) : next()
    )
    .catch(next);
});

// ── Start server ──────────────────────────────────────────────────────────────
if (isMainModule(import.meta.url) || process.env['pm_id']) {
  const port = process.env['PORT'] || 4000;
  app.listen(port, (error) => {
    if (error) throw error;
    console.log(`Node Express server listening on http://localhost:${port}`);
    console.log(`Proxying API requests to: ${BACKEND_INTERNAL_URL}`);
  });
}

export const reqHandler = createNodeRequestHandler(app);