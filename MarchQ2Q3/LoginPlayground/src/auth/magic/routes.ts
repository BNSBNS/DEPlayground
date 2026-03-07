import { Router } from "express";
import { showRequestPage, handleSend, handleVerify, showSuccess } from "./handlers.js";

const router = Router();

// Show the email input form
router.get("/request", showRequestPage);

// Send magic link email
router.post("/send", handleSend);

// Verify magic link token (clicked from email)
router.get("/verify", handleVerify);

// Post-verification success page
router.get("/profile", showSuccess);

export { router as magicRoutes };
