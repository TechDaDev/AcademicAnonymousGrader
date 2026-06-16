# Academic Anonymous Grader — Final Acceptance Checklist

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Ready for Sign-Off
- **Last Updated:** 2026-06-16

## Instructions
This checklist documents formal acceptance of the Academic Anonymous Grader version 1.0.0 release. Each area must be reviewed and signed off by the designated reviewer.

| # | Acceptance Area | Status | Reviewer Role | Date | Comments | Signature |
|---|-----------------|--------|---------------|------|----------|-----------|
| 1 | Functional Acceptance | □ Pending □ Pass □ Fail | | | | |
| 2 | Privacy Acceptance | □ Pending □ Pass □ Fail | | | | |
| 3 | Security Acceptance | □ Pending □ Pass □ Fail | | | | |
| 4 | Deployment Acceptance | □ Pending □ Pass □ Fail | | | | |
| 5 | Backup Acceptance | □ Pending □ Pass □ Fail | | | | |
| 6 | Restore Acceptance | □ Pending □ Pass □ Fail | | | | |
| 7 | Update Acceptance | □ Pending □ Pass □ Fail | | | | |
| 8 | Documentation Acceptance | □ Pending □ Pass □ Fail | | | | |
| 9 | Training Acceptance | □ Pending □ Pass □ Fail | | | | |
| 10 | Governance Acceptance | □ Pending □ Pass □ Fail | | | | |
| 11 | Release-Package Acceptance | □ Pending □ Pass □ Fail | | | | |
| 12 | Project-Closure Acceptance | □ Pending □ Pass □ Fail | | | | |

## Acceptance Definitions

### 1. Functional Acceptance
Confirms that the application performs its intended functions:
- User authentication and role-based access.
- Material and assessment management.
- Secure import with identity encryption.
- Anonymous grading workflow.
- Review and finalization.
- Identity-bearing and de-identified export.
- Analytics and reporting.
- Academic structure management.
- Audit logging.

### 2. Privacy Acceptance
Confirms that privacy protections are effective:
- Identities encrypted at rest.
- Grading uses anonymous codes only.
- Logs exclude identity data.
- Audit metadata is privacy-safe.
- Exports follow role permissions.
- Diagnostic bundle excludes sensitive data.

### 3. Security Acceptance
Confirms security controls are in place:
- Encryption key validation.
- Fingerprint key separation.
- Password hashing (bcrypt).
- No hardcoded credentials.
- No secrets in image, backups, or diagnostic bundles.
- Backup validation prevents traversal and unexpected members.
- Role-based access enforcement.

### 4. Deployment Acceptance
Confirms deployment procedures work:
- Fresh installation completes.
- Docker image builds and contains no secrets.
- Compose file uses production defaults.
- Health check passes.
- Post-install validation passes.
- Offline installation works.

### 5. Backup Acceptance
Confirms backup procedures:
- Backup creates valid archive.
- Manifest contains version and schema.
- Checksums validate.
- Two unique backup references created.
- No excluded content (`.env`, secrets, logs).

### 6. Restore Acceptance
Confirms restore procedures:
- Restore from verified backup succeeds.
- Data counts match pre-restore state.
- Identities decrypt after restore.
- Health passes after restore.
- Pre-restore backup is created automatically.

### 7. Update Acceptance
Confirms update procedures:
- rc1 → 1.0.0 update tested and verified.
- Pre-update backup created.
- Data preserved.
- Keys preserved.
- Schema compatible.

### 8. Documentation Acceptance
Confirms documentation is complete:
- All required documents present (25+ items).
- Instructions use exact commands and filenames.
- Policies are clearly defined.
- Training materials are actionable.

### 9. Training Acceptance
Confirms training materials are ready:
- Administrator training checklist complete.
- Instructor training checklist complete.
- Materials cover all required topics.

### 10. Governance Acceptance
Confirms governance framework is defined:
- Governance policy established.
- Key-custody policy documented.
- Backup/recovery policy defined.
- Access-control policy defined.
- Data-governance policy defined.
- Incident-response plan documented.
- Audit-review procedure defined.
- Maintenance plan documented.
- Support model established.

### 11. Release-Package Acceptance
Confirms the release package is complete:
- All required files included.
- Checksums validate.
- Manifest values consistent with VERSION, schema, image tag.
- No secrets, credentials, or local paths.
- SBOM included.

### 12. Project-Closure Acceptance
Confirms the project is ready to close:
- All completed phases documented.
- Skipped phases noted.
- Test results recorded.
- Handover archive prepared.
- Closure report written.

## Summary

| Total Areas | Passed | Failed | Pending |
|-------------|--------|--------|---------|
| 12 | | | 12 |

## Final Approval

**Project Closure Approved By:**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Project Owner | | | |
| Technical Lead | | | |
| Quality Assurance | | | |
| Institutional Representative | | | |
