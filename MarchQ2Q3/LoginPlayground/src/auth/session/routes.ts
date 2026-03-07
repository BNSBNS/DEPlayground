import { Router } from "express";
import { handleLogin, handleLogout, showLoginPage, showProfile } from "./handlers.js";

const router = Router();

// Show the login form
router.get("/login", showLoginPage);

// Process login: validate credentials, create session
router.post("/login", handleLogin);

// Show profile (requires active session)
router.get("/profile", showProfile);

// Logout: destroy session
router.post("/logout", handleLogout);

export { router as sessionRoutes };
