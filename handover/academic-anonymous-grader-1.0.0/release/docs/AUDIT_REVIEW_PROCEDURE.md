# Academic Anonymous Grader — Audit-Review Procedure

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Purpose
This procedure defines how system audit logs are reviewed to detect unauthorized access, configuration changes, and suspicious activity.

## 2. Review Schedule
- **Routine review:** Monthly.
- **Pre-assessment review:** Before and after high-stakes assessment periods.
- **Incident-triggered review:** Immediately after any security incident.

## 3. Audit Events to Review

| Event Type | What to Check | Suspicious Pattern |
|------------|---------------|--------------------|
| Logins | Timestamp, username, success/failure | Repeated failures, logins at unusual hours |
| Failed authentication | Count per user, source | Brute-force pattern (>5 failures in 5 minutes) |
| User creation | New username, role, who created | Unexpected new accounts |
| Role changes | Old role, new role, who changed | Elevation to Administrator without authorization |
| Imports | File count, identity count, user | Bulk imports outside normal schedule |
| Identity resolution | Manual decisions | Unusual match/skip/create patterns |
| Assessment finalization | Assessment, user, timestamp | Finalizations outside assessment schedule |
| Identity-bearing exports | Export type, row count, user | Exports without documented request |
| Academic structure changes | What changed, who changed | Unexpected deletions |
| Backup creation | Backup ref, user | Backups outside schedule |
| Restore operations | Backup ref, user | Unauthorized restore attempts |
| Deployment updates | Old version, new version | Unapproved version changes |
| Destructive actions | Delete/archive operations | Bulk deletions |

## 4. Review Steps
1. Log in to the application as Administrator.
2. Navigate to the Audit page.
3. Filter by the review period.
4. Scan for events matching the suspicious patterns in the table above.
5. For each suspicious event, investigate by:
   - Checking the event timestamp and user.
   - Cross-referencing with any documented approval (e.g., import schedule, export request).
   - Contacting the user if needed.
6. Document findings in the review log.
7. Escalate confirmed issues to the Incident Coordinator.

## 5. Privacy-Safe Audit Handling
- Audit records are viewed within the application only.
- Audit data is never included in diagnostic bundles by default.
- Audit logs are not exported for review outside the application without Data Protection Officer approval.
- When discussing audit findings, use user IDs, not personal names.

## 6. Issue Escalation
- Confirmed suspicious activity → notify the Incident Coordinator.
- Potential unauthorized data access → notify the Institutional System Owner and Data Protection Officer.
- System integrity concern → notify Technical Administrator.

## 7. Audit Retention
- Audit events are retained indefinitely in the database.
- The database size should be monitored for growth.
- An Administrator may archive or trim audit records when the table becomes large, following institutional policy.

## 8. Prohibited Audit Metadata
Audit records must not contain:
- Plaintext identity data.
- Grade values.
- Feedback content.
- Passwords or password hashes.
- Encryption keys or key material.

## 9. Reviewer Sign-Off Template

```
Audit Review — [Date]
Review period: [start] to [end]
Reviewed by: [role/initials]
Events reviewed: [count]
Suspicious events found: [count]
Issues escalated: [count]
Comments:
_________________________
Signature: _________________________
```
