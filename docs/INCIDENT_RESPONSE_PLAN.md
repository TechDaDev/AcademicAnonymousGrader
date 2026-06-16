# Academic Anonymous Grader — Incident-Response Plan

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. General Response Procedure
For every incident, follow this sequence:
1. **Detect** — Identify that an incident has occurred or is in progress.
2. **Contain** — Limit the scope and impact. Stop the application if necessary.
3. **Preserve Evidence** — Capture logs, audit records, and system state before taking corrective action.
4. **Assess** — Determine severity, affected data, and root cause.
5. **Recover** — Restore normal operation.
6. **Notify** — Inform the appropriate roles.
7. **Document** — Record the incident, actions taken, and lessons learned.
8. **Prevent Recurrence** — Implement changes to prevent similar incidents.

## 2. Suspected Key Exposure
- **Detect:** Unauthorized access to `.env` file, unexpected decryption errors, or known key disclosure.
- **Contain:** Stop the application immediately. Revoke any discovered unauthorized access.
- **Preserve:** Copy the current `.env` to secure offline storage for evidence. Copy current audit logs.
- **Assess:** Determine which keys were exposed and for how long. Assess whether the database or backups were accessed.
- **Recover:** If database was not accessed, pre-exposure backup may be restored. If identities were accessed, follow institutional breach-notification procedure. Create new keys and re-encrypt identities (manual process).
- **Notify:** Institutional System Owner, Data Protection Officer.
- **Document:** Record the exposure scope, time, and remediation steps.
- **Prevent:** Review key-storage procedures. Retrain custodians.

## 3. Lost Key
- **Detect:** Application fails to start with key-validation error. Administrator cannot access identity data.
- **Contain:** N/A — data is already inaccessible.
- **Preserve:** Search all authorized locations for backup copies.
- **Assess:** Is there a backup copy of `.env`? If not, identities are permanently lost.
- **Recover:** If backup `.env` exists, restore it. If not, the installation must be treated as fresh. Previous backups with that key are unrecoverable.
- **Notify:** Institutional System Owner, Data Protection Officer.
- **Document:** Record the loss and outcome.
- **Prevent:** Implement off-device key backup per Key-Custody Policy.

## 4. Exposed Backup
- **Detect:** Backup file found in an unauthorized location or accessed by unauthorized person.
- **Contain:** Secure the exposed backup. Change the backup password.
- **Preserve:** Log the exposure details.
- **Assess:** Determine if the backup contained encrypted identities and whether the corresponding `.env` was also exposed.
- **Recover:** If both backup and `.env` were exposed, identities may be decrypted. Follow institutional breach-notification procedure. If only the backup was exposed, identities remain encrypted.
- **Notify:** Institutional System Owner, Data Protection Officer.
- **Document:** Record the exposure.
- **Prevent:** Review backup-storage procedures. Ensure backups are encrypted.

## 5. Unauthorized Identity Export
- **Detect:** Audit log shows identity-bearing export at unusual time or by unexpected user.
- **Contain:** Deactivate the user account. Review recent exports.
- **Preserve:** Copy the audit records. Locate any exported files.
- **Assess:** What data was exported? Who received it? For what purpose?
- **Recover:** Attempt to retrieve and secure exported files. Assess institutional notification obligations.
- **Notify:** Institutional System Owner, Data Protection Officer.
- **Document:** Record the unauthorized export.
- **Prevent:** Review user permissions. Reinforce training on identity-handling policy.

## 6. Account Compromise
- **Detect:** Audit log shows unusual activity from a user account (odd hours, unexpected actions, failed logins).
- **Contain:** Deactivate the compromised account. Reset all active sessions.
- **Preserve:** Copy audit records and login timestamps.
- **Assess:** What actions were performed by the compromised account? Was any data accessed or exported?
- **Recover:** Restore any altered data from backup if needed. Create a new account for the legitimate user with the same permissions. Conduct password reset.
- **Notify:** Affected user, Institutional System Owner.
- **Document:** Record the compromise scope.
- **Prevent:** Enforce strong passwords. Review account-security practices.

## 7. Suspicious Audit Activity
- **Detect:** Audit review reveals unexpected patterns (bulk imports at odd hours, repeated failed logins, role changes without authorization).
- **Contain:** Investigate the specific events.
- **Preserve:** Preserve the relevant audit records.
- **Assess:** Are the events explained by legitimate activity? If not, escalate.
- **Recover:** Address any confirmed issues (reset accounts, revert unauthorized changes).
- **Notify:** Institutional System Owner.
- **Document:** Record findings.
- **Prevent:** Adjust audit-review frequency during high-risk periods.

## 8. Failed Migration
- **Detect:** Migration script fails with an error. Application does not start.
- **Contain:** Do not force-start the application without the migration.
- **Preserve:** Copy the migration log and database before any attempted recovery.
- **Assess:** Is the migration script defect or a database issue? Can the migration be safely re-run?
- **Recover:** Restore the pre-upgrade database backup. Re-apply the migration after the defect is fixed.
- **Notify:** Technical Administrator.
- **Document:** Record the migration failure.
- **Prevent:** Test migrations on a copy of the database before applying to production.

## 9. Corrupted Database
- **Detect:** Application crashes, health check fails, or database queries return errors.
- **Contain:** Stop the application.
- **Preserve:** Copy the database file for forensic analysis.
- **Assess:** Is the database fixable (SQLite integrity check)? Determine the cause.
- **Recover:** Restore from the most recent verified backup.
- **Notify:** Technical Administrator, Backup Custodian.
- **Document:** Record the corruption details.
- **Prevent:** Ensure regular verified backups. Check disk health.

## 10. Accidental Volume Deletion
- **Detect:** Application data volumes are missing. Application fails to start.
- **Contain:** Do not recreate volumes with new data.
- **Preserve:** Check Docker volume list immediately.
- **Assess:** Were the volumes deleted? Were backups available?
- **Recover:** Restore from the most recent verified backup.
- **Notify:** Technical Administrator.
- **Document:** Record the deletion.
- **Prevent:** Review destructive command procedures. Use `docker compose down` without `-v` by default.

## 11. Wrong-Key Startup
- **Detect:** Application starts but identity decryption fails.
- **Contain:** Stop the application.
- **Preserve:** Keep the wrong `.env` file for reference.
- **Assess:** Which `.env` was loaded? Where is the correct `.env`?
- **Recover:** Replace the `.env` with the correct one. Restart.
- **Notify:** Key Custodian.
- **Document:** Record the incident.
- **Prevent:** Label `.env` files clearly. Maintain a key-custody log.

## 12. Public-Network Exposure
- **Detect:** Application accessible from unexpected IP ranges.
- **Contain:** Change firewall rules or stop the application.
- **Preserve:** Capture access logs.
- **Assess:** Was any data accessed by unauthorized parties?
- **Recover:** Secure the network. Change all passwords. Review for unauthorized access.
- **Notify:** Institutional System Owner, Data Protection Officer.
- **Document:** Record the exposure.
- **Prevent:** Follow the Production Checklist for network configuration.

## 13. Grading-Data Integrity Issue
- **Detect:** Grades or feedback appear incorrect or inconsistent.
- **Contain:** Prevent finalization of affected assessments.
- **Preserve:** Copy the current grading data.
- **Assess:** What went wrong? Was it human error or a system defect?
- **Recover:** If not finalized, grades can be corrected within the application. If finalized, re-open the assessment or use a backup.
- **Notify:** Academic Program Administrator.
- **Document:** Record the issue.
- **Prevent:** Review grading workflows. Add validation checks where feasible.

## 14. Unauthorized Role Assignment
- **Detect:** Audit log shows a user was assigned a role without documented authorization.
- **Contain:** Revert the role assignment.
- **Preserve:** Audit log entries.
- **Assess:** Who performed the assignment? Was the action malicious or mistaken?
- **Recover:** Return affected user(s) to previous role(s).
- **Notify:** Institutional System Owner.
- **Document:** Record the incident.
- **Prevent:** Review Administrator training. Enforce separation of duties.

## 15. Legal Notification
This incident-response plan does not define legal notification deadlines. Institutional legal and privacy officers determine external reporting obligations in accordance with applicable regulations (e.g., GDPR, FERPA, local privacy laws).

## 16. Plan Review
Review this plan after any significant incident and at least annually.
