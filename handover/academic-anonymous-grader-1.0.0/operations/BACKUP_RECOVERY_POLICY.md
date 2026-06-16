# Academic Anonymous Grader — Backup and Recovery Policy

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Policy Scope
This policy covers backup and recovery for the Academic Anonymous Grader production installation, including the application database, configuration, and encryption keys.

## 2. Backup Ownership
- **Primary Backup Custodian:** Technical Administrator (or designee).
- **Secondary (Off-Device) Custodian:** Institutional System Owner or designee.
- Backup Custodians should be separate from Key Custodians where practical.

## 3. Backup Schedule

| Backup Type | Frequency | Retention | Owner |
|-------------|-----------|-----------|-------|
| Automated database backup | Daily during active grading | 7 most recent | Backup Custodian |
| Off-device verified copy | Weekly | 4 most recent | Secondary Custodian |
| Pre-upgrade backup | Before each update | Until next update confirmed stable | Technical Administrator |
| Pre-restore backup | Before each restore | Until restore verified successful | Technical Administrator |
| Monthly restore-test backup | Monthly | 6 most recent | Backup Custodian |

## 4. Backup Contents
Each backup archive contains:
- `database.sqlite` — the full SQLite database.
- `manifest.json` — metadata including backup reference, application version (1.0.0), schema version, database hash, table list, and creation timestamp.

The `.env` file is **never** included in backup archives by design.

## 5. Verification Requirements
- Every backup must be verified immediately after creation.
- Verification checks: archive integrity, manifest presence, database hash match, schema compatibility.
- A verified backup is one where the SHA-256 hash of the embedded database matches the manifest's `database_hash`.

## 6. Recovery-Time Objective (RTO)
- **Recommended RTO:** 4 hours for full recovery from a verified backup.
- Actual time depends on backup size, network transfer speed for off-device copies, and operator familiarity.

## 7. Recovery-Point Objective (RPO)
- **Recommended RPO:** 24 hours (daily backup during active grading periods).
- Data entered between the last backup and a failure may be lost.

## 8. Restore Procedure
1. Confirm the target `.env` matches the keys used when the backup was created.
2. Create a pre-restore backup automatically (the restore script does this).
3. Verify the backup checksum and manifest.
4. Stop the application.
5. Execute the restore.
6. Restart the application.
7. Verify health.
8. Verify data counts.
9. Verify encrypted identity decryption.

## 9. Pre-Upgrade and Pre-Restore Backups
The system automatically creates a pre-upgrade or pre-restore backup before any destructive operation. These backups are retained until the next upgrade confirms stability, then may be pruned.

## 10. Recovery from Corruption
If the database is corrupted:
1. Determine the most recent verified backup.
2. Confirm the corresponding `.env` is available.
3. Run the restore procedure.
4. If the most recent backup is also corrupt, attempt the next previous backup.
5. If no backup is usable, contact Level 3 support.

## 11. Disaster-Recovery Procedure
For complete system loss (server failure, laptop destruction):
1. Install the same application version on new hardware.
2. Generate a new `.env` (temporary).
3. Restore the original `.env` from secure secondary storage.
4. Load the most recent verified off-device backup.
5. Run migrations.
6. Verify health, counts, and identity decryption.

## 12. Backup Disposal
- Backups containing encrypted identity data must be disposed of securely when they exceed their retention period.
- Use `docker volume rm` for local Docker volume backups.
- For off-device copies, use institutional secure-deletion procedures.

## 13. Off-Device Copy Expectations
- At least one copy of the most recent verified backup should be stored off the primary device.
- Off-device copies should be encrypted at rest.
- The corresponding `.env` must be stored securely alongside the backup (but not inside it).

## 14. Policy Review
This policy should be reviewed:
- At least annually.
- After any restore incident.
- After any significant system architecture change.
