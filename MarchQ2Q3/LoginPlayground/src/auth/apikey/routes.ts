import { Router } from "express";
import { showGeneratePage, handleGenerate, showTestPage, handleProtected } from "./handlers.js";

const router = Router();

// Show the key generation page
router.get("/generate", showGeneratePage);

// Generate a new API key
router.post("/generate", handleGenerate);

// Show the test page (input field for key)
router.get("/test", showTestPage);

// Protected endpoint: requires valid X-API-Key header
router.get("/protected", handleProtected);

export { router as apikeyRoutes };
