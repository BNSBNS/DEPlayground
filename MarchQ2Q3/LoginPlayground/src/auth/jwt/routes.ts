import { Router } from "express";
import { showLoginPage, handleLogin, handleRefresh, showProtected } from "./handlers.js";

const router = Router();

// Show the login form
router.get("/login", showLoginPage);

// Process login: validate credentials, issue JWT pair
router.post("/login", handleLogin);

// Refresh: rotate refresh token, issue new access token
router.post("/refresh", handleRefresh);

// Protected resource: requires valid Bearer token
router.get("/protected", showProtected);

export { router as jwtRoutes };
