# ADR-0013: SSO / RBAC via Agency IdP (Keycloak OIDC / SAML & CAC/PIV) and OSS vs Enterprise Assessment

## Status
Accepted

## Context
Project Argus requires enterprise-grade Single Sign-On (SSO) and Role-Based Access Control (RBAC) (Feature F016) to satisfy federal cybersecurity mandates (NIST SP 800-53 AC-2/AC-3, NIST SP 800-63-3 AAL3) and agency PIV/CAC smart card authentication requirements.

### OSS vs. Enterprise Assessment for SigNoz & Grafana
1. **SigNoz OSS vs Enterprise**:
   - In the SigNoz Community/OSS distribution (`v0.145.0`), authentication is local SQLite-based (`/var/lib/signoz/signoz.db`). SAML/OIDC SSO, SCIM provisioning, and multi-team granular RBAC are locked behind proprietary Enterprise licensing.
   - Commercial enterprise licenses require either outbound internet connectivity to vendor license servers or periodic offline license file exchanges, violating strict air-gap compliance principles and introducing proprietary supply-chain risks.
2. **Air-Gapped Federal Solution (OIDC Reverse Proxy Architecture)**:
   - Rather than relying on closed-source enterprise binary extensions, Project Argus standardizes on an air-gapped, zero-trust OIDC/SAML Auth Gateway (`argus-sso-gateway`) deployed as an in-cluster Policy Enforcement Point (`PEP`) in front of the observability UI and APIs.
   - The Agency Identity Provider (`argus-idp`, compatible with Keycloak, Active Directory Federation Services, and PingFederate) handles primary credential verification, PIV/CAC certificate extraction, and multi-factor authentication (MFA).
   - Upon successful IdP authentication, the gateway verifies the cryptographic signature of the OIDC token, extracts agency group memberships and CAC/PIV assurance claims, maps them to Argus RBAC roles, enforces route-level permissions, and propagates tenant headers to upstream services.

## Decision
1. **Deploy In-Cluster Agency Identity Provider (`argus-idp`)**:
   - Runs in `argus-system` using `localhost:5001/argus/python:3.12-alpine` on port `8089`.
   - Exposes standard OIDC endpoints:
     - `GET /.well-known/openid-configuration`: OpenID Provider Configuration Document.
     - `GET /protocol/openid-connect/certs`: JWKS endpoint exposing public keys.
     - `POST /protocol/openid-connect/token`: Token issuance with HMAC-SHA256 / RSA cryptographic signing, role assertions, and expiration timestamps.
     - `GET /protocol/openid-connect/userinfo`: Identity claims provider.
   - Provides pre-configured agency user identities with simulated PIV/CAC AAL3 authentication:
     - `alice.admin@dhs.gov`: Member of `dhs-soc-admins` -> Role `Admin`.
     - `bob.operator@dhs.gov`: Member of `dhs-soc-operators` -> Role `Operator` (`Editor`).
     - `carol.viewer@dhs.gov`: Member of `dhs-soc-viewers` -> Role `Viewer`.
     - `mallory.unassigned@dhs.gov`: Member of `dhs-general-staff` -> No monitoring role assigned.
2. **Deploy Agency SSO & RBAC Gateway (`argus-sso-gateway`)**:
   - Runs in `argus-system` using `localhost:5001/argus/python:3.12-alpine` on port `8088`.
   - Functions as an authenticated reverse proxy to SigNoz (`http://signoz:8080`) and Argus management APIs.
   - **RBAC Matrix**:
     | Role | Read Telemetry (Traces/Logs/Metrics) | Silence / Acknowledge Alerts | Mutate Rules / Dashboards | Administer Tenancy & Users |
     | :--- | :---: | :---: | :---: | :---: |
     | **Admin** | YES | YES | YES | YES |
     | **Operator** | YES | YES | Personal Only | NO |
     | **Viewer** | YES | NO | NO | NO |
     | **NoAccess** | NO (403) | NO (403) | NO (403) | NO (403) |
   - Enforces cryptographic token signature verification, non-expired validity checks (`exp > now`), and route-level mutation blocks (rejecting write requests from `Viewer` with HTTP 403 Forbidden).
   - Injects `X-Scope-TenantID` and `X-Forwarded-User` headers to guarantee multi-tenant isolation (F015).
3. **Resilience & Security Controls**:
   - Clock-skew tolerance bounded to 30 seconds.
   - Cryptographic signature tampering explicitly rejected with HTTP 401.
   - Complete audit logging of authorization decisions.

## Consequences
- **Positive**:
  - Full compliance with federal PIV/CAC and OIDC authentication standards without proprietary enterprise licenses.
  - Granular RBAC enforcement (Admin, Operator, Viewer) protecting sensitive monitoring controls from unauthorized modification.
  - Multi-tenant boundary preservation through automatic tenant scope propagation.
  - 100% air-gap compliant with zero external dependencies.
- **Negative / Trade-offs**:
  - Upstream UI components must trust identity headers injected by the secure gateway proxy.
