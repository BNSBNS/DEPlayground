import { Router } from "express";
import { handleLogin, handleAcs, showProfile } from "./handlers.js";

const router = Router();

// Initiate SAML login: build AuthnRequest, redirect to IdP
router.get("/login", handleLogin);

// Assertion Consumer Service: IdP POSTs SAMLResponse here
router.post("/acs", handleAcs);

// Show profile with decoded SAML assertion attributes
router.get("/profile", showProfile);

export { router as samlRoutes };
