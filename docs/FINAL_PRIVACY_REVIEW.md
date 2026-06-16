# Academic Anonymous Grader — Final Privacy Review

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Reviewed
- **Last Updated:** 2026-06-16

## 1. Reviewed Areas

| Area | Review Finding | Verdict |
|------|----------------|---------|
| Identity lifecycle | Identities are encrypted on import, stored encrypted, and decrypted only during authorized export. No plaintext storage. | PASS |
| Import | Identities encrypted immediately on import. Source-grade is informational-only. Fingerprints used for matching. | PASS |
| Encryption | AES-256-GCM with random nonces. Each field encrypted separately. Key validated at startup. | PASS |
| Pseudonymization | Anonymous codes generated per student per assessment. No reversible mapping exposed during grading. | PASS |
| Grading | Instructors see only anonymous codes. No name, email, or ID visible. | PASS |
| Analytics | Aggregate analytics only. No individual identity data exposed. Privacy thresholds enforced (minimum group size). | PASS |
| Audit | Events track user actions. No plaintext identity, grades, or feedback in audit records. | PASS |
| Export | Identity-bearing export requires Administrator role. De-identified export available. | PASS |
| Backup | Backup archives contain encrypted identity data. `.env` excluded from backup. Key required to access identities. | PASS |
| Diagnostic bundle | Excludes: `.env`, keys, passwords, identities, names, emails, institutional IDs, responses, grades, feedback, ciphertext, fingerprints, database contents. | PASS |
| Release artifacts | No secrets, credentials, or identity data in release package. | PASS |
| Testing | Tests use synthetic fixtures. No real student data in test files. | PASS |
| Git privacy | No `.env`, databases, secrets, or identity data tracked in Git. | PASS |
| Deletion | No bulk identity-deletion UI. Manual database access required for deletion. Backup retention may outlive data deletion. | PASS |

## 2. Residual Privacy Risks

| Risk | Mitigation | Accepted? |
|------|------------|-----------|
| Administrator could export identities without authorization | Audit trail records all exports. Policy requires authorization. | Yes |
| Backup archive contains encrypted identities (if `.env` also exposed) | Key-Custody Policy separates key and backup custody. Backup excludes `.env`. | Yes |
| Instructor could attempt to identify students despite prohibition | Training checklist addresses this. Policy violation consequences are institutional. | Yes |
| Formula injection in exported XLSX | Prefix protection applied to cells starting with `=`, `+`, `-`, `@`. | Yes |
| Grades visible in exports | Exports are controlled by Administrator role. | Yes |

## 3. Operational Mitigations
- Audit logs enable post-hoc review of all identity-bearing operations.
- Role-based access limits identity exposure to trusted Administrator roles.
- Regular audit review is recommended to detect unauthorized activity.
- The diagnostic bundle can be generated and inspected before sharing with support.

## 4. Final Privacy Verdict
**PASS** — The application implements privacy by design: identities are encrypted at rest, grading is anonymous, analytics are aggregate, audit is metadata-only, and diagnostic bundles exclude sensitive data. Residual privacy risks are documented and accepted.
