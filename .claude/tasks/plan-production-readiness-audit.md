# Implementation Plan: Production Readiness + Security Hardening

Created: 2025-12-27
Status: APPROVED - EXECUTING

## Summary

Maximum security hardening + Azure OpenAI integration + Vercel/Railway deployment. The app needs to be "Mariana Trench tight" - no security holes, no exposed secrets, bulletproof authentication. Users will be manually provisioned in Supabase (no self-registration).

## Azure OpenAI Configuration (CONFIRMED)

```
Endpoint: https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com
Deployments:
  - gpt-41 (chat) → API version 2025-01-01-preview
  - gpt-41-mini (chat) → API version 2025-01-01-preview
  - text-embedding-ada-002 (embeddings) → API version 2023-05-15
```

## Deployment Stack (CONFIRMED)

| Component | Platform | URL | Cost |
|-----------|----------|-----|------|
| Frontend | Vercel | foresight.vercel.app | Free tier |
| Backend | Railway | TBD (e.g., foresight-api.up.railway.app) | $5 free credit/month |
| Database | Supabase | Already configured | Free tier |
| Auth | Supabase Auth | Already configured | Free tier |

**Railway Pricing**: $5 free credit/month, then pay-as-you-go (~$0.000231/min). For a small app like this, likely stays under $5/month.

---

## Scope

### In Scope
- **SECURITY HARDENING** (Priority 1)
  - Supabase RLS policy audit
  - Rate limiting on all API endpoints
  - Security headers (HSTS, CSP, X-Frame-Options, etc.)
  - Input validation on all endpoints
  - JWT validation hardening
  - Audit logging for sensitive operations
- Azure OpenAI integration (Azure-only, no fallback)
- Vercel deployment configuration
- Railway backend deployment (Dockerfile hardening)
- CORS lockdown (only foresight.vercel.app)
- Console.log cleanup
- Environment variable security

### Out of Scope
- Self-registration (manual user provisioning only)
- New features
- Azure AD SSO (future)

---

## Implementation Phases

### Phase 1: Security Hardening (CRITICAL)
**Objective**: Lock down the application - Mariana Trench security

**Parallel Tasks**:

1. **Task 1A: Backend Security Middleware**
   - Add rate limiting (slowapi or similar)
   - Add security headers middleware
   - Add request ID logging for audit trail
   - Validate all JWT tokens properly
   - Add IP-based suspicious activity detection
   - Owns: `backend/app/main.py` (middleware section), `backend/app/security.py` (new)

2. **Task 1B: Supabase RLS Audit**
   - Verify RLS enabled on ALL tables
   - Verify policies prevent cross-user data access
   - Ensure service key usage is minimal and justified
   - Document RLS policies
   - Owns: `supabase/migrations/` (audit only), `docs/SECURITY.md` (new)

3. **Task 1C: Input Validation Hardening**
   - Add Pydantic validators to all request models
   - Add field length limits
   - Sanitize all user inputs
   - Prevent SQL injection (verify parameterized queries)
   - Owns: `backend/app/main.py` (Pydantic models)

4. **Task 1D: Frontend Security**
   - Remove all console.log/debug statements
   - Add CSP meta tags
   - Ensure no secrets in client bundle
   - Verify auth token handling is secure
   - Owns: `frontend/foresight-frontend/src/**/*.tsx`, `frontend/foresight-frontend/index.html`

**New Files to Create**:
- `backend/app/security.py` - Security utilities, rate limiting
- `docs/SECURITY.md` - Security documentation

**Phase Verification**:
- [ ] Rate limiting blocks >100 requests/minute from single IP
- [ ] Invalid JWT returns 401 immediately
- [ ] RLS prevents user A from seeing user B's data
- [ ] No console.log in production build
- [ ] Security headers present in all responses

---

### Phase 2: Azure OpenAI Integration
**Objective**: Switch from OpenAI direct to Azure OpenAI endpoints

**Parallel Tasks**:

1. **Task 2A: Azure OpenAI Provider**
   - Create `backend/app/openai_provider.py` with Azure client
   - Configure deployment name mapping:
     - `gpt-4o` → `gpt-41`
     - `gpt-4o-mini` → `gpt-41-mini`
     - `text-embedding-ada-002` → `text-embedding-ada-002`
   - Use correct API versions per endpoint type
   - Owns: `backend/app/openai_provider.py` (new), `backend/app/main.py` (client init)

2. **Task 2B: Update AI Service References**
   - Replace hardcoded model names with config
   - Update ai_service.py to use provider
   - Update brief_service.py to use provider
   - Owns: `backend/app/ai_service.py`, `backend/app/brief_service.py`

3. **Task 2C: Environment Configuration**
   - Update .env.example with Azure variables
   - Remove OpenAI fallback (Azure-only)
   - Add startup validation for required Azure vars
   - Owns: `backend/.env.example`

**Environment Variables Required**:
```
AZURE_OPENAI_ENDPOINT=https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_EMBEDDING_API_VERSION=2023-05-15
AZURE_OPENAI_DEPLOYMENT_CHAT=gpt-41
AZURE_OPENAI_DEPLOYMENT_CHAT_MINI=gpt-41-mini
AZURE_OPENAI_DEPLOYMENT_EMBEDDING=text-embedding-ada-002
```

**Phase Verification**:
- [ ] App starts with Azure config only
- [ ] Chat completions work via Azure
- [ ] Embeddings work via Azure
- [ ] Missing Azure config = startup failure (not silent fallback)

---

### Phase 3: Deployment Configuration
**Objective**: Production-ready deployment to Vercel + Railway

**Parallel Tasks**:

1. **Task 3A: Vercel Frontend Config**
   - Create `vercel.json` with SPA routing
   - Configure environment variables
   - Add security headers in vercel.json
   - Owns: `frontend/foresight-frontend/vercel.json` (new)

2. **Task 3B: Railway Backend Config**
   - Harden Dockerfile (non-root user, health check)
   - Add gunicorn for production
   - Create railway.json or Procfile
   - Owns: `backend/Dockerfile`, `backend/railway.json` (new)

3. **Task 3C: CORS Lockdown**
   - Set ALLOWED_ORIGINS to only `https://foresight.vercel.app`
   - Remove localhost from production
   - Add strict CORS validation
   - Owns: `backend/app/main.py` (CORS section)

**vercel.json**:
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

**Phase Verification**:
- [ ] Vercel preview deployment works
- [ ] Railway deployment works with health check
- [ ] CORS blocks requests from non-allowed origins
- [ ] All security headers present

---

### Phase 4: Final Security Review
**Objective**: Comprehensive security audit before launch

**Sequential Tasks**:

1. **Task 4A: Penetration Testing Checklist**
   - Test authentication bypass attempts
   - Test authorization (access other users' data)
   - Test rate limiting
   - Test input validation (SQL injection, XSS)
   - Test API without auth token
   - Document findings

2. **Task 4B: Secrets Audit**
   - Verify no secrets in git history
   - Verify no secrets in client bundle
   - Verify .env files in .gitignore
   - Document all required secrets

**Phase Verification**:
- [ ] All penetration tests pass
- [ ] No secrets exposed
- [ ] Security documentation complete

---

## Security Checklist (Mariana Trench Level)

### Authentication & Authorization
- [ ] JWT tokens validated on EVERY protected endpoint
- [ ] Token expiration enforced
- [ ] Refresh token rotation implemented
- [ ] Supabase RLS on ALL tables
- [ ] No endpoint returns data for wrong user

### API Security
- [ ] Rate limiting: 100 req/min per IP
- [ ] Request size limits
- [ ] Input validation on all fields
- [ ] Parameterized queries (no SQL injection)
- [ ] Error messages don't leak internals

### Transport Security
- [ ] HTTPS only (no HTTP)
- [ ] HSTS header enabled
- [ ] Secure cookies (HttpOnly, Secure, SameSite)

### Headers
- [ ] X-Frame-Options: DENY
- [ ] X-Content-Type-Options: nosniff
- [ ] Content-Security-Policy configured
- [ ] Referrer-Policy: strict-origin-when-cross-origin

### Secrets
- [ ] No secrets in code
- [ ] No secrets in git history
- [ ] Environment variables for all credentials
- [ ] .env in .gitignore

### Logging & Monitoring
- [ ] Audit log for auth events
- [ ] Audit log for data modifications
- [ ] Error logging (without sensitive data)
- [ ] Request IDs for tracing

---

## File Ownership Matrix

| File | Owner | Phase |
|------|-------|-------|
| backend/app/main.py (middleware) | Task 1A | 1 |
| backend/app/main.py (Pydantic) | Task 1C | 1 |
| backend/app/main.py (client init) | Task 2A | 2 |
| backend/app/main.py (CORS) | Task 3C | 3 |
| backend/app/security.py | Task 1A | 1 |
| backend/app/openai_provider.py | Task 2A | 2 |
| backend/app/ai_service.py | Task 2B | 2 |
| backend/app/brief_service.py | Task 2B | 2 |
| backend/.env.example | Task 2C | 2 |
| backend/Dockerfile | Task 3B | 3 |
| frontend/foresight-frontend/vercel.json | Task 3A | 3 |
| frontend/foresight-frontend/src/**/*.tsx | Task 1D | 1 |
| docs/SECURITY.md | Task 1B | 1 |

---

## Rollback Plan

1. **Security changes**: All additive, can disable middleware
2. **Azure OpenAI**: Can revert to OpenAI by changing env vars
3. **Deployment**: Can redeploy previous version

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Security headers | All present |
| Rate limiting | Working |
| RLS policies | Verified on all tables |
| Azure OpenAI | All calls successful |
| Vercel deploy | Working |
| Railway deploy | Working |
| Auth bypass | Impossible |
| Data leakage | Impossible |

---

**STATUS: APPROVED - READY FOR EXECUTION**
