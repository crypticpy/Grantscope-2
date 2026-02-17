#!/usr/bin/env python3
"""Generate JWT keys for self-hosted PostgREST + GoTrue.

Usage:
    python infra/generate_keys.py                    # Generate new secret + keys
    python infra/generate_keys.py <jwt_secret>       # Use existing secret

Output: environment variables to add to backend/.env
"""

import json
import sys
import base64
import hmac
import hashlib
import secrets


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_jwt(payload: dict, secret: str) -> str:
    """Create a minimal HS256 JWT (no external dependencies)."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64url_encode(signature)
    return f"{signing_input}.{sig_b64}"


def main():
    # Use provided secret or generate a new one
    if len(sys.argv) > 1:
        jwt_secret = sys.argv[1]
    else:
        jwt_secret = secrets.token_hex(32)

    if len(jwt_secret) < 32:
        print("ERROR: JWT secret must be at least 32 characters", file=sys.stderr)
        sys.exit(1)

    # Generate service_role key (used by backend — bypasses RLS)
    service_key = create_jwt(
        {
            "role": "service_role",
            "iss": "grantscope",
            "iat": 0,
            "exp": 253402300800,  # Year 9999
        },
        jwt_secret,
    )

    # Generate anon key (used by frontend — respects RLS)
    anon_key = create_jwt(
        {
            "role": "anon",
            "iss": "grantscope",
            "iat": 0,
            "exp": 253402300800,
        },
        jwt_secret,
    )

    print(
        "# ============================================================================="
    )
    print("# GrantScope2 — Self-Hosted JWT Configuration")
    print(
        "# ============================================================================="
    )
    print("# Add these to backend/.env and frontend/.env")
    print(
        "# The JWT_SECRET must be identical across PostgREST, GoTrue, and this config."
    )
    print(
        "# ============================================================================="
    )
    print()
    print(f"JWT_SECRET={jwt_secret}")
    print()
    print("# Backend (backend/.env)")
    print(f"SUPABASE_SERVICE_KEY={service_key}")
    print(f"SUPABASE_ANON_KEY={anon_key}")
    print()
    print("# Frontend (frontend/foresight-frontend/.env)")
    print(f"VITE_SUPABASE_ANON_KEY={anon_key}")
    print()
    print("# PostgREST + GoTrue (set in docker-compose.yml or Azure Container Apps)")
    print(f"PGRST_JWT_SECRET={jwt_secret}")
    print(f"GOTRUE_JWT_SECRET={jwt_secret}")


if __name__ == "__main__":
    main()
