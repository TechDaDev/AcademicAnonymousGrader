# Academic Anonymous Grader — Support Model

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Support Levels

### Level 1 — End-User Support
Provided by: Designated institutional support contact.

Covers:
- Login issues (forgotten password, account locked).
- Navigation guidance.
- Basic installation status (is the application running?).
- User guidance (how to grade, how to view results).
- Known-problem resolution from the known-error database.

Escalation to Level 2: When the issue requires configuration changes or data operations.

### Level 2 — Technical Support
Provided by: Technical Administrator or designee.

Covers:
- Backup and restore operations.
- Docker container management (start, stop, restart, logs).
- Configuration changes (`.env` validation, port changes).
- Permission and role issues.
- Import/export troubleshooting.
- Import file format issues.
- Academic structure management.

Escalation to Level 3: When the issue appears to be a code defect, data-integrity issue, or cryptographic failure.

### Level 3 — Development Support
Provided by: Development team (original project developers or designated maintainer).

Covers:
- Code defects requiring a patch or hotfix.
- Migration defects or failures.
- Cryptographic or key-management failures.
- Data-integrity incidents.
- Feature requests for future releases.

## 2. Required Diagnostic Information
When requesting support, provide:
1. Application version (from `VERSION` file or status script).
2. Schema version (from `database.migrations.SCHEMA_VERSION`).
3. Docker version (`docker version`).
4. Compose version (`docker compose version`).
5. Container status (`docker compose ps`).
6. Health check result (`python -m scripts.health_check`).
7. A diagnostic bundle if Level 2 or Level 3 support requests it.

## 3. Diagnostic Bundle Use
- The diagnostic bundle contains safe aggregate information only.
- It may be shared with support personnel.
- It never contains: secrets, keys, passwords, identities, responses, grades, feedback, ciphertext, or database content.
- Generate with: `python -m scripts.create_diagnostic_bundle`.

## 4. Prohibited Information to Send
When contacting support, do **not** include:
- `.env` file contents.
- Encryption keys or fingerprint keys.
- Passwords.
- Student names, emails, or IDs.
- Grade rosters or individual grades.
- Database files.
- Backup archives.

## 5. Escalation Path
```
End User ──> Level 1 (Support Contact)
                │
                ├── Resolved? ──> Close
                │
                └── Escalate ──> Level 2 (Technical Administrator)
                                  │
                                  ├── Resolved? ──> Close
                                  │
                                  └── Escalate ──> Level 3 (Development Team)
```

- Level 1 contacts Level 2 when unable to resolve.
- Level 2 contacts Level 3 through documented support channels.
- All escalations should include the diagnostic bundle and a summary of steps already taken.

## 6. Response-Priority Categories

| Priority | Description | Target Initial Response |
|----------|-------------|------------------------|
| Critical | System down, data loss, security incident | Within 4 hours |
| High | Feature blocked, major workflow cannot proceed | Within 1 business day |
| Medium | Non-blocking issue, workaround available | Within 3 business days |
| Low | Cosmetic issue, documentation request | Within 5 business days |

These are recommendations, not guaranteed response times. Actual response times depend on institutional support resources.

## 7. Known-Error Recording
- Known errors and their resolutions should be documented.
- The known-error database should be maintained by Level 1 support.
- Before escalating an issue, check the known-error database.

## 8. Closure Criteria
An issue is considered closed when:
- The reported problem is resolved.
- The user has confirmed the resolution.
- The resolution is documented in the known-error database if applicable.
- No further action is required.
