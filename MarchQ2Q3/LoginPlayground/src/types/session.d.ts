// Consolidated session type declarations for all auth methods.
// All properties that any auth handler stores in the session are declared here.

import "express-session";

declare module "express-session" {
  interface SessionData {
    // Session-based auth
    userId?: string;
    email?: string;
    authMethod?: string;

    // OIDC
    oidcState?: string;
    oidcCodeVerifier?: string;
    oidcIdToken?: string;
    oidcClaims?: Record<string, unknown>;

    // Entra ID
    entraState?: string;
    entraCodeVerifier?: string;
    entraIdToken?: string;
    entraClaims?: Record<string, unknown>;

    // SAML
    samlRelayState?: string;
    samlAttributes?: Record<string, string>;
    samlNameId?: string;
    samlRawAssertion?: string;
  }
}
