#!/usr/bin/env python3
"""
Argus Agency Identity Provider (IdP) & OIDC Token Issuer
Simulates an enterprise Keycloak / ADFS / PIV/CAC-backed identity provider.
Provides:
1. OIDC Discovery (/.well-known/openid-configuration).
2. JWKS Certs (/protocol/openid-connect/certs).
3. Token issuance (/protocol/openid-connect/token) supporting CAC/PIV claims and role mapping.
4. Userinfo (/protocol/openid-connect/userinfo).
5. Health checks (/healthz).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import signal
import sys
import time
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", "8089"))
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
ISSUER = os.environ.get("OIDC_ISSUER", "http://argus-idp.argus-system.svc.cluster.local:8089")
AUDIENCE = os.environ.get("OIDC_AUDIENCE", "argus-platform")
MAX_TOKEN_LIFETIME_SECONDS = int(os.environ.get("MAX_TOKEN_LIFETIME_SECONDS", "3600"))
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "https://argus.dhs.gov,http://localhost:8080,http://localhost:8088"
    ).split(",") if o.strip()
]

# Pre-provisioned Agency User Directory (NIST SP 800-63-3 AAL3 CAC/PIV verified)
USERS_DB = {
    "alice.admin@dhs.gov": {
        "password": os.environ.get("IDP_ADMIN_PASSWORD", "admin_pass"),
        "name": "Alice Vance (SOC Admin)",
        "preferred_username": "alice.admin",
        "groups": ["dhs-soc-admins", "dhs-all-staff"],
        "roles": ["Admin"],
        "tenant_id": "default",
        "piv_card_id": "PIV-948102-DHS",
        "acr": "nist-800-63-3-aal3"
    },
    "bob.operator@dhs.gov": {
        "password": os.environ.get("IDP_OPERATOR_PASSWORD", "operator_pass"),
        "name": "Bob Miller (SOC Operator)",
        "preferred_username": "bob.operator",
        "groups": ["dhs-soc-operators", "dhs-all-staff"],
        "roles": ["Operator"],
        "tenant_id": "tenant_alpha",
        "piv_card_id": "PIV-551029-DHS",
        "acr": "nist-800-63-3-aal3"
    },
    "carol.viewer@dhs.gov": {
        "password": os.environ.get("IDP_VIEWER_PASSWORD", "viewer_pass"),
        "name": "Carol Danvers (Analyst Viewer)",
        "preferred_username": "carol.viewer",
        "groups": ["dhs-soc-viewers", "dhs-all-staff"],
        "roles": ["Viewer"],
        "tenant_id": "tenant_beta",
        "piv_card_id": "PIV-110294-DHS",
        "acr": "nist-800-63-3-aal3"
    },
    "center.ops@dhs.gov": {
        "password": os.environ.get("IDP_CENTER_PASSWORD", "center_pass"),
        "name": "Center Ops (SOC Center)",
        "preferred_username": "center.ops",
        "groups": ["dhs-soc-center", "dhs-all-staff"],
        "roles": ["Operator"],
        "tenant_id": "tenant_center",
        "piv_card_id": "PIV-773301-DHS",
        "acr": "nist-800-63-3-aal3"
    },
    "mallory.unassigned@dhs.gov": {
        "password": os.environ.get("IDP_UNASSIGNED_PASSWORD", "unassigned_pass"),
        "name": "Mallory Unassigned (Contractor)",
        "preferred_username": "mallory.unassigned",
        "groups": ["dhs-general-staff"],
        "roles": ["NoAccess"],
        "tenant_id": "unassigned",
        "piv_card_id": "PIV-000000-TEMP",
        "acr": "nist-800-63-3-aal1"
    }
}

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)

def _get_jwt_secret(secret: str = None) -> str:
    val = secret if secret is not None else os.environ.get("JWT_SECRET", JWT_SECRET)
    return (val or "").strip()

def create_signed_jwt(payload: dict, secret: str = None) -> str:
    signing_secret = _get_jwt_secret(secret)
    if not signing_secret:
        raise RuntimeError("JWT_SECRET is unset; failing closed on token signing")
    header = {"alg": "HS256", "typ": "JWT", "kid": "argus-idp-key-1"}
    h_b64 = b64url_encode(json.dumps(header).encode("utf-8"))
    p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(signing_secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{b64url_encode(sig)}"

def verify_signed_jwt(token: str, secret: str = None) -> tuple[bool, dict, str]:
    signing_secret = _get_jwt_secret(secret)
    if not signing_secret:
        return False, {}, "Server signing key is not configured"
    parts = token.split(".")
    if len(parts) != 3:
        return False, {}, "Malformed token format"
    try:
        h_b64, p_b64, s_b64 = parts
        header = json.loads(b64url_decode(h_b64).decode("utf-8"))
        if not isinstance(header, dict) or header.get("alg") != "HS256" or header.get("typ") not in (None, "JWT"):
            return False, {}, "Unsupported or invalid JWT algorithm"
        msg = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(signing_secret.encode("utf-8"), msg, hashlib.sha256).digest()
        actual_sig = b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, {}, "Invalid cryptographic signature"
        payload = json.loads(b64url_decode(p_b64).decode("utf-8"))
        if not isinstance(payload, dict):
            return False, {}, "Invalid token claims payload"
        now = int(time.time())
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)) or exp < now:
            return False, payload, "Token has expired"
        nbf = payload.get("nbf")
        if nbf is not None and (not isinstance(nbf, (int, float)) or now < int(nbf) - 5):
            return False, payload, "Token is not yet valid (nbf)"
        iss = payload.get("iss")
        if iss is not None and iss != ISSUER:
            return False, payload, "Invalid token issuer"
        aud = payload.get("aud")
        if aud is not None:
            valid_aud = (aud == AUDIENCE) if isinstance(aud, str) else (isinstance(aud, list) and AUDIENCE in aud)
            if not valid_aud:
                return False, payload, "Invalid token audience"
        return True, payload, ""
    except Exception as e:
        return False, {}, f"Token decode error: {e}"


class IdPRequestHandler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def finish(self):
        try:
            super().finish()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/healthz":
            self.send_json(200, {"status": "ok", "service": "argus-idp"})
            return

        # OIDC Discovery endpoint
        if path == "/.well-known/openid-configuration":
            config = {
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
                "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
                "userinfo_endpoint": f"{ISSUER}/protocol/openid-connect/userinfo",
                "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
                "response_types_supported": ["code", "token", "id_token"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["HS256"],
                "scopes_supported": ["openid", "email", "profile", "roles"],
                "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
                "claims_supported": ["sub", "iss", "aud", "nbf", "exp", "iat", "email", "name", "preferred_username", "roles", "groups", "tenant_id", "piv_card_id", "acr"]
            }
            self.send_json(200, config)
            return

        # JWKS certs endpoint
        if path == "/protocol/openid-connect/certs":
            jwks = {
                "keys": [
                    {
                        "kid": "argus-idp-key-1",
                        "kty": "oct",
                        "alg": "HS256",
                        "use": "sig"
                    }
                ]
            }
            self.send_json(200, jwks)
            return

        # Userinfo endpoint
        if path == "/protocol/openid-connect/userinfo":
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self.send_json(401, {"error": "unauthorized", "message": "Missing Bearer token"})
                return
            token = auth_header.split(" ", 1)[1].strip()
            valid, payload, err = verify_signed_jwt(token)
            if not valid:
                self.send_json(401, {"error": "invalid_token", "message": err})
                return
            self.send_json(200, payload)
            return

        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # OIDC Token endpoint
        if path == "/protocol/openid-connect/token":
            if not _get_jwt_secret():
                self.send_json(500, {"error": "server_error", "error_description": "IdP signing key is not configured"})
                return

            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len)

            # Can be application/x-www-form-urlencoded or application/json
            content_type = self.headers.get("Content-Type", "")
            params = {}
            if "application/json" in content_type:
                try:
                    params = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    params = {}
            else:
                parsed_qs = urllib.parse.parse_qs(body_bytes.decode("utf-8"))
                params = {k: v[0] for k, v in parsed_qs.items()}

            if not isinstance(params, dict):
                self.send_json(400, {"error": "invalid_request", "error_description": "Invalid request payload"})
                return

            username = params.get("username", "")
            password = params.get("password", "")

            if not username or not isinstance(username, str) or not password or not isinstance(password, str):
                self.send_json(401, {"error": "invalid_grant", "error_description": "Username and password are required"})
                return

            # Authenticate against mock user directory (constant-time password check, non-empty required)
            user_data = USERS_DB.get(username)
            if not user_data:
                self.send_json(401, {"error": "invalid_grant", "error_description": "Unknown user identity"})
                return

            expected_password = user_data.get("password", "")
            if not expected_password or not hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8")):
                self.send_json(401, {"error": "invalid_grant", "error_description": "Invalid credentials"})
                return

            try:
                requested_expiry = int(params.get("expires_in", "3600"))
            except (ValueError, TypeError):
                self.send_json(400, {"error": "invalid_request", "error_description": "Invalid expires_in value"})
                return

            if requested_expiry <= 0:
                self.send_json(400, {"error": "invalid_request", "error_description": "expires_in must be positive"})
                return

            # Enforce strict server-side maximum token lifetime cap (H4)
            effective_expiry = min(requested_expiry, MAX_TOKEN_LIFETIME_SECONDS)

            now = int(time.time())
            exp = now + effective_expiry

            claims = {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "sub": user_data["preferred_username"],
                "email": username,
                "name": user_data["name"],
                "preferred_username": user_data["preferred_username"],
                "groups": user_data["groups"],
                "roles": user_data["roles"],
                "tenant_id": user_data["tenant_id"],
                "piv_card_id": user_data["piv_card_id"],
                "acr": user_data["acr"],
                "amr": ["piv", "mfa"] if user_data["acr"] == "nist-800-63-3-aal3" else ["pwd"],
                "iat": now,
                "nbf": now,
                "exp": exp,
                "jti": secrets.token_hex(16)
            }

            access_token = create_signed_jwt(claims)
            id_token = create_signed_jwt(claims)

            self.send_json(200, {
                "access_token": access_token,
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": effective_expiry,
                "scope": "openid email profile roles",
                "roles": user_data["roles"],
                "tenant_id": user_data["tenant_id"]
            })
            return

        self.send_json(404, {"error": "not found"})


def run():
    if not _get_jwt_secret():
        sys.stderr.write("ERROR: JWT_SECRET environment variable must be set before starting argus-idp.\n")
        sys.exit(1)

    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, IdPRequestHandler)
    httpd.daemon_threads = True

    def handle_shutdown(signum, frame):
        sys.stderr.write(f"Argus IdP received signal {signum}, shutting down cleanly...\n")
        try:
            httpd.server_close()
        except Exception:
            pass
        os._exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    sys.stderr.write(f"Argus Agency IdP listening on port {PORT} (Issuer: {ISSUER})...\n")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
