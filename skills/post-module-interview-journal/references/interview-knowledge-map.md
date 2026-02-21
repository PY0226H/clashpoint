# Interview Knowledge Map

## Rust Backend
- Auth and security
  - JWT claims, expiry strategy, key rotation
  - Middleware order and trust boundary
  - CORS least privilege and token leakage prevention
- Reliability
  - Replace `unwrap/expect` in request path
  - Error mapping strategy (`4xx` vs `5xx`)
  - Timeout/retry/circuit-breaking decisions
- Data and consistency
  - Transaction boundaries
  - Idempotency and race-condition handling
  - Migration rollback strategy
- Performance
  - Streaming instead of full-memory loading
  - Connection pool sizing and backpressure

## Frontend / Tauri
- Auth state
  - Why avoid localStorage for long-lived tokens
  - Cookie session tradeoffs for web and desktop
- Security
  - CSP policy design
  - Tauri capability minimization
- UX and stability
  - SSE reconnect/backoff strategy
  - Error-state handling and fallback flows

## DevOps / Engineering Excellence
- CI/CD
  - Required quality gates (lint, test, e2e, build)
  - Release and rollback checklist
- Observability
  - Correlation/request id
  - Structured logging and sensitive data redaction
  - SLO, alerting thresholds, incident response

## Frequently Asked Follow-up Questions
- Why this design, not alternatives?
- What did you break during implementation, and how did you recover?
- How did you validate correctness and non-regression?
- If traffic grows 10x, what breaks first?
- If onboarding a new teammate, what docs are enough to hand over this module?
