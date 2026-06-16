# Academic Anonymous Grader — Known Limitations

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Accepted Limitations
These limitations are known and accepted for version 1.0.0:

### Deployment
- **Local or controlled-network deployment only.** The application is not designed for direct public-internet exposure without additional security measures (reverse proxy, firewall, VPN).
- **SQLite database.** SQLite has inherent limitations with concurrent write access. The application is designed for single-server deployments with a limited number of concurrent users.
- **Single-server architecture.** Horizontal scaling is not supported.
- **No automatic cloud backup.** Off-device backup requires manual procedures.
- **No external monitoring integration.** Health checks must be performed manually or via external monitoring tools that can check HTTP endpoints.

### Authentication
- **No SSO/LDAP integration.** User accounts are managed within the application.
- **No multi-factor authentication.** Password-based authentication only.
- **Password-reset is manual.** An Administrator must reset forgotten passwords.

### Integration
- **No LMS integration.** Import and export are file-based.
- **No API.** All operations are performed through the web UI or deployment scripts.
- **No webhook support.**

### Academic Features
- **One current academic year at a time.** Multiple concurrent academic years are supported, but the classification model (academic stages, departments) is institution-specific and configured during setup.
- **Institution-specific stage and term limits.** The default seed data (3 departments, 4 stages, 2 terms) may need adjustment for each institution.
- **Forward-only schema migrations.** Once a migration is applied, it cannot be reverted without a database restore.

### Grading
- **No AI grading.** Phase 11 (AI grading) was intentionally not implemented.
- **No live collaboration.** Grading is individual; real-time collaborative grading is not supported.
- **No offline grading mode.** The application must be accessible during grading sessions.

### Identity Management
- **No automated key rotation.** Replacing encryption keys requires manual re-import of all identities.
- **Key recovery depends on secure `.env` backup.** Lost keys make encrypted identities permanently unreadable.
- **No bulk identity deletion.** Identity records must be deleted manually through database access.

### Backup and Restore
- **Restore requires original keys.** Restoring a backup without the matching `.env` will make identities unreadable.
- **No incremental backups.** Each backup is a full database snapshot.
- **No automatic restore testing.** Restore rehearsals are manual.

### Browser
- **Browser interaction required.** The application is a Streamlit web UI; automated batch operations are not supported.
- **Optimized for modern browsers.** Older browsers may not be fully supported.

## 2. Future Optional Improvements
These are potential improvements for future versions, not commitments:

- Key rotation with re-encryption support.
- SSO/LDAP/2FA authentication.
- LMS integration (LTI, REST API).
- PostgreSQL/MySQL database support.
- Public-cloud deployment documentation.
- Automated off-device backup.
- Monitoring and alerting integration.
- Bulk identity management UI.
- Enhanced analytics and reporting.
- Multi-language support.

## 3. Out-of-Scope Items
The following were explicitly excluded from the project scope:

- **Phase 11 — AI Grading.** AI-assisted or automated grading was intentionally not implemented.
- **Phase 14 — Institutional Pilot.** An institutional pilot was skipped by project-owner decision.
- **Phase 16 — Optional Integrations.** Integration with external systems (LMS, SIS, identity providers) is outside the closed project scope.
- **Real-time collaboration.** Live multi-user editing is not supported.
- **Mobile application.** No native mobile client is provided.
- **White-labeling or reskinning.** The application UI is not designed for extensive customization.
