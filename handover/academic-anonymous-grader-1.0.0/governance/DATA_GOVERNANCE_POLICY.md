# Academic Anonymous Grader — Data-Governance Policy

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Data Categories

| Category | Description | Sensitivity | Retention |
|----------|-------------|-------------|-----------|
| Identity data | Student name, email, institutional ID | High — encrypted at rest | Until academic purpose ends; per institutional policy |
| Anonymous grading data | Anonymous codes, submissions, responses | Medium | Until academic purpose ends |
| Academic metadata | Materials, assessments, academic structure | Low | Permanent for historical reference |
| Grades | Scored results | Medium | Until academic purpose ends |
| Feedback | Instructor comments on submissions | Medium | Until academic purpose ends |
| Audit metadata | Login, import, export, finalization records | Low–Medium | Minimum 1 year, per institutional policy |
| Backups | Full database snapshots | High (contain encrypted identities) | Per Backup and Recovery Policy |
| Exports | Finalized results (may include identities) | High | Per institutional data-retention policy |
| Logs | Application logs, health checks | Low | 30 days rolling |

## 2. Identity Data Protection
- All identity fields are encrypted at rest using AES-256-GCM.
- Encryption keys are stored in `.env`, never in the database.
- Identity matching uses HMAC-SHA256 fingerprints, not plaintext.
- Grading services use only anonymous IDs — they never receive plaintext identity.
- Identity restoration occurs only through controlled Administrator export.

## 3. Anonymous Grading
- Each student is assigned a unique anonymous code per assessment.
- Instructors see only the anonymous code during grading.
- The mapping between identity and anonymous code is stored encrypted.
- The mapping is revealed only during identity-bearing export by an Administrator.

## 4. Data Minimization
- Only required identity fields are collected: name, email, and/or institutional ID.
- No biometric data, national IDs, or sensitive personal data (beyond names and institutional contact information) should be imported.
- Import templates should contain only the columns required for grading.

## 5. Export Controls
- Exports may be identity-bearing (including decrypted student identities) or de-identified (anonymous codes only).
- Identity-bearing exports require Administrator privileges.
- Exported files are written to the designated exports volume.
- Export files should be retrieved and stored according to institutional data-protection policies.

## 6. Import Controls
- Imported files are parsed, identities are encrypted immediately.
- Source files should be deleted from the upload system after successful import.
- Source-grade data in imports is informational only.

## 7. Backup Data
- Backups contain encrypted identity data.
- Backups are excluded from containing `.env`, keys, passwords, or logs.
- Backup archives must be stored securely.

## 8. Audit Data
- Audit events track: logins, failed logins, user creation, role changes, imports, identity resolution, finalization, exports, academic structure changes, backups, restores, updates, and destructive actions.
- Audit records do not include plaintext identity data, grades, or feedback content.
- Audit records include: timestamp, user ID, action, target, and result (success/failure with reason code).

## 9. Log Data
- Application logs exclude: identity values, grades, feedback, and full request bodies.
- Logs may include: timestamps, usernames (for auth events), page names, and error types.
- Logs are written to the designated logs volume.
- Default retention: 30 days rolling.

## 10. Test-Data Restrictions
- Tests use synthetic or sanitized fixture data only.
- Real student data must never be committed to Git.
- Sample files contain only fictional placeholder data.
- Test databases are created per-test and discarded.

## 11. Data Deletion
- The application does not implement bulk student-data deletion.
- To delete identity data, an Administrator must manually truncate the relevant tables (offline, with database access).
- Anonymous grading data may be retained for audit purposes even after identity data is deleted.
- Backup archives may still contain deleted data until they reach their retention limit.

## 12. Secure Disposal
- When the system is decommissioned, the database file must be securely wiped.
- All backup copies must be disposed of using institutional secure-deletion procedures.
- The `.env` file must be securely destroyed.
- Exported result files must be disposed of according to institutional policy.

## 13. Formula-Injection Protection
- Exported XLSX files prefix cells beginning with `=`, `+`, `-`, or `@` with a leading space to prevent formula injection.
- The application validates that exported data does not contain executable spreadsheet content.

## 14. Policy Review
Review this policy annually and after any privacy-impacting system change.
