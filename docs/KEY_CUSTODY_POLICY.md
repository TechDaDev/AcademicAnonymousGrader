# Academic Anonymous Grader — Key-Custody Policy

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Key Inventory

| Key | Purpose | Algorithm | Length | Format |
|-----|---------|-----------|--------|--------|
| `IDENTITY_ENCRYPTION_KEY` | AES-256-GCM encryption of student PII | AES-256-GCM | 32 bytes | URL-safe base64 |
| `IDENTITY_FINGERPRINT_KEY` | HMAC-SHA256 fingerprinting for identity matching | HMAC-SHA256 | 32+ bytes | URL-safe base64 |
| `BACKUP_PASSWORD` | Password protection for backup archives | – | 32 hex chars | Hex string (64 chars) |

## 2. Key Requirements
- `IDENTITY_ENCRYPTION_KEY` and `IDENTITY_FINGERPRINT_KEY` **must be different**.
- Keys must be generated using a cryptographically secure random source.
- The application validates key format and difference at startup.
- If keys are identical, the application refuses to start with a `SameKeyError`.

## 3. Database–Key Pairing
- Each database instance is paired with its `.env` file.
- The encryption key encrypts identity data in that specific database.
- Restoring a database backup without the original `.env` will make identities unreadable.
- The `IDENTITY_ENCRYPTION_KEY` and `IDENTITY_FINGERPRINT_KEY` in `.env` must match the keys that were active when the identities were originally encrypted.

## 4. Authorized Custodians
Key custody must be assigned by the Institutional System Owner. The minimum recommended custodians are:
- **Primary Key Custodian** — holds the production `.env`.
- **Secondary Key Custodian** — holds a securely backed-up copy.

## 5. Secure Storage Requirements
Keys must be stored:
- Outside the application repository.
- Outside shared network drives accessible to unauthorized personnel.
- In a location with access control.
- Encrypted at rest where possible.
- Backed up using institutional secrets-management procedures.

## 6. Backup Copy Policy
- One backup copy of `.env` should be maintained by the Secondary Key Custodian.
- Backup copies must use the same storage protections as the primary.
- Backup copies must be tested periodically by loading them into a test environment.

## 7. Key Transfer Between Laptops
When moving the installation to another laptop:
1. Export the database backup from the source.
2. Securely transfer the `.env` file (the "Secrets Package") separately from the database backup.
3. Import the database backup into the target installation.
4. Replace the target's auto-generated `.env` with the source `.env`.
5. Verify that identities decrypt correctly.
6. Destroy the intermediate transfer copies.

See `docs/MOVE_TO_ANOTHER_LAPTOP.md` for detailed steps.

## 8. Rotation Limitations
- **Key rotation is not supported for existing encrypted identities.**
- Replacing the encryption key will make all previously encrypted identity data unreadable.
- Key rotation requires re-importing all student data under a new key, which is a manual process outside the scope of the current release.
- The fingerprint key similarly cannot be rotated without re-fingerprinting all existing identities.

## 9. Lost-Key Consequences
If the `.env` file is lost and no backup copy exists:
- All encrypted identity fields become permanently unreadable.
- Anonymous grading codes remain usable (they are not encrypted with identity keys).
- Academic data, grades, and feedback remain intact.
- Student identities cannot be reconstructed.
- The installation must be treated as a fresh installation with new keys.
- Previous backups remain encrypted with the lost key and cannot be restored.

## 10. Compromised-Key Response
If key exposure is suspected:
1. Immediately stop the application.
2. Assess the scope: which keys were exposed, for how long.
3. Notify the Institutional System Owner and Data Protection Officer.
4. If identities were accessed, follow institutional breach-notification procedures.
5. If only the `.env` file was exposed but no database was accessed, replace keys (see Rotation Limitations) or restore from a pre-exposure backup.
6. Document the incident in the audit trail.

## 11. Prohibited Storage Locations
Keys must **never** be stored in:
- Git repositories.
- Email messages or attachments.
- Chat systems (Teams, Slack, WhatsApp, etc.).
- Plaintext files on shared drives.
- Screenshots or photographs.
- Code comments.
- Log files.
- Diagnostic bundles.
- Backup archives (`.env` is excluded from backup by design).

## 12. Periodic Custody Review
- The Key Custodian should confirm key location and accessibility every 90 days.
- A custody-review log should be maintained.
- If the Custodian changes, keys must be transferred using a secure handoff procedure.
