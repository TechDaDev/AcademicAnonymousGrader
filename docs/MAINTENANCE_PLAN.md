# Academic Anonymous Grader — Maintenance Plan

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Routine Maintenance Tasks

| Frequency | Task | Owner | Procedure |
|-----------|------|-------|-----------|
| Daily (active grading) | Verify application health | Technical Administrator | `python -m deployment.checks.post_install` |
| Daily (active grading) | Create automated backup | Backup Custodian | `deployment/windows/backup.ps1` or `linux/backup.sh` |
| Weekly | Create off-device verified backup copy | Backup Custodian | Backup script + copy to secure off-device storage |
| Weekly | Review disk usage | Technical Administrator | `docker info` (storage) or OS disk monitoring |
| Monthly | Full restore rehearsal | Technical Administrator | Restore backup to test environment, verify data |
| Monthly | User-account review | Technical Administrator | Navigate to Users page, verify active/inactive users |
| Monthly | Audit-log review | Audit Reviewer | Follow Audit-Review Procedure |
| Monthly | Key-custody check | Key Custodian | Verify `.env` backup location and integrity |
| Monthly | Backup-verification test | Backup Custodian | Verify backup checksum, restore to test environment |
| Quarterly | Dependency review | Technical Administrator | Check Python package updates (see Section 5) |
| Quarterly | Docker/Compose version review | Technical Administrator | Verify minimum versions are met |
| Quarterly | OS security updates | Technical Administrator | Apply OS patches to the host |
| Annually | Policy review | Institutional System Owner | Review all governance policies |
| Annually | Full restore rehearsal with off-device backup | Backup Custodian | Simulate complete disaster recovery |

## 2. Pre-Maintenance Checklist
Before any maintenance operation:
1. Create a verified backup.
2. Confirm the current `.env` is backed up.
3. Test the procedure on a non-production copy first if possible.
4. Schedule maintenance during low-activity periods.

## 3. Release Update Procedure
1. Review the release notes.
2. Create a pre-upgrade backup.
3. Test the update on an isolated copy first.
4. Schedule the update window.
5. Notify users of expected downtime.
6. Perform the update using `update.ps1` or `update.sh`.
7. Verify health, data counts, and identity decryption.
8. Monitor for issues for 24 hours before confirming stability.
9. Retain the pre-upgrade backup until stability is confirmed.

## 4. Emergency Patch Procedure
1. Assess the severity: is the issue blocking grading or exposing data?
2. Create a pre-patch backup.
3. Apply the minimal fix required.
4. Rebuild the Docker image.
5. Update the application.
6. Verify fix and health.
7. Document the emergency patch.
8. Schedule a proper release if the fix is permanent.

## 5. Dependency Update Policy
- Dependencies should not be updated without testing.
- Before updating a dependency, check the release notes for breaking changes.
- Test the update on an isolated copy before production.
- Each update should be accompanied by a verified backup.
- Major-version updates require full regression testing.

## 6. Support Lifecycle

| Version | Status | Support Level |
|---------|--------|---------------|
| 1.0.x | Active | Full support |
| 0.x | End of life | No support |

## 7. End-of-Life Procedure
When a version reaches end of life:
1. Notify all users at least 90 days in advance.
2. Provide upgrade instructions.
3. Offer migration assistance.
4. After the end-of-life date, stop providing patches.
5. Archive the release documentation.

## 8. Maintenance Log
Maintain a log of all maintenance activities including:
- Date and time.
- Description of the activity.
- Person performing the activity.
- Result (success/failure).
- Backup reference (if applicable).
- Follow-up actions required.
