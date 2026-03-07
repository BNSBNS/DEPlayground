import { Router } from "express";
import { handleLogin, handleCallback, showProfile } from "./handlers.js";

const router = Router();

// Initiate OIDC login: build /authorize URL, redirect to Keycloak
router.get("/login", handleLogin);

// Keycloak redirects back here with ?code=...&state=...
router.get("/callback", handleCallback);

// Show profile with decoded ID token claims
router.get("/profile", showProfile);

export { router as oidcRoutes };
