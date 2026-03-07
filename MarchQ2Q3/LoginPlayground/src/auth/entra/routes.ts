import { Router } from "express";
import { handleLogin, handleCallback, showProfile } from "./handlers.js";

const router = Router();

// Initiate Entra ID login: same OIDC flow, different realm
router.get("/login", handleLogin);

// Keycloak (entra realm) redirects back here
router.get("/callback", handleCallback);

// Show profile with groups, roles, tenant claims
router.get("/profile", showProfile);

export { router as entraRoutes };
