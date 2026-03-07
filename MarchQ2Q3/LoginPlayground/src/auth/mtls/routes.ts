import { Router } from "express";
import { showTestPage, handleProtected } from "./handlers.js";

const router = Router();

// Show instructions for testing mTLS with curl
router.get("/test", showTestPage);

// Protected endpoint: requires valid client certificate
router.get("/protected", handleProtected);

export { router as mtlsRoutes };
