# Academic Anonymous Grader — Governance Policy

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Purpose
This policy defines roles, responsibilities, and separation of duties for operating the Academic Anonymous Grader system in a production environment.

## 2. Roles and Responsibilities

### Institutional System Owner
- Holds overall responsibility for the system within the institution.
- Approves major policy changes and release acceptance.
- Designates the Technical Administrator and Data Protection Officer.
- Receives escalation for incidents beyond the Technical Administrator's authority.

### Technical Administrator
- Manages day-to-day system operation.
- Creates and manages user accounts.
- Assigns roles (Administrator, Grader, Reviewer, Viewer, Exporter).
- Performs installations, updates, backups, and restores.
- Manages academic structure (departments, stages, terms, academic years).
- Oversees secure imports and identity resolution.
- Manages assessment finalization and identity-bearing exports.
- Reviews audit logs.
- Responds to operational incidents.
- Must not share Administrator credentials.

### Data Protection Officer (DPO)
- Advises on privacy obligations.
- Reviews privacy-impacting changes.
- Handles data-subject requests where applicable.
- Reviews audit logs monthly.
- Participates in incident response involving potential identity exposure.

### Academic Program Administrator
- Creates materials and assessments.
- Assigns instructors to assessments.
- Manages academic classification.
- Coordinates import schedules with instructors.
- Reviews analytics for program-level insight.

### Instructor
- Grades assigned anonymous work only.
- Provides feedback.
- Views own progress and scoped analytics.
- Never accesses student identities.
- Reports suspected identity exposure immediately.
- Cannot manage users, imports, finalization, exports, backups, or academic structure.

### Backup Custodian
- Performs scheduled backups.
- Verifies backup integrity.
- Maintains off-device backup copies.
- Reports backup failures to the Technical Administrator.
- May be the same person as the Technical Administrator but should be a separate role where practical.

### Key Custodian
- Stores and protects encryption keys, fingerprint keys, and backup passwords.
- Transfers keys only through approved secure channels.
- Never stores keys in Git, email, chat, or shared drives.
- Participates in key rotation or recovery when authorized.
- Must be a separate person from the Backup Custodian where practical.

### Release Approver
- Reviews release packages before production deployment.
- Confirms test results, security review, and documentation completeness.
- Authorizes the final release commit and tag.

### Incident Coordinator
- Leads incident response.
- Contacts the System Owner, DPO, and Key Custodian as needed.
- Documents the incident and resolution.
- Recommends preventive measures.

### Audit Reviewer
- Reviews system audit logs on a defined schedule.
- Identifies suspicious activity.
- Escalates findings to the Incident Coordinator.
- May be the DPO or a designated compliance officer.

### Support Contact
- Receives Level 1 support requests.
- Triages to Level 2 or Level 3 as needed.
- Maintains the known-error database.

## 3. Separation of Duties
The following combinations should be avoided where practical:
- The same person acting as Data Protection Officer and Key Custodian.
- The same person acting as Release Approver and sole Developer.
- The same person performing import and finalization of the same assessment.
- An Administrator grading their own assigned assessments.

## 4. Authorization Matrix

| Action | Admin | Grader | Reviewer | Viewer | Exporter |
|--------|-------|--------|----------|--------|----------|
| Create users | ✓ | – | – | – | – |
| Assign roles | ✓ | – | – | – | – |
| Manage academic structure | ✓ | – | – | – | – |
| Create materials/assessments | ✓ | – | – | – | – |
| Import submissions | ✓ | – | – | – | – |
| Resolve identity matching | ✓ | – | – | – | – |
| Grade assigned work | ✓ | ✓ | – | – | – |
| Review/finalize assessments | ✓ | – | ✓ | – | – |
| Export identities | ✓ | – | – | – | ✓ |
| View audit logs | ✓ | – | – | – | – |
| Manage backups/restore | ✓ | – | – | – | – |
| View analytics | ✓ | ✓ | ✓ | ✓ | ✓ |
| View identities | ✓ | – | – | – | (export) |
| Manage settings | ✓ | – | – | – | – |

## 5. Policy Review
This policy should be reviewed:
- At least annually.
- After any major incident.
- After any significant system change.
- When institutional data-governance requirements change.
