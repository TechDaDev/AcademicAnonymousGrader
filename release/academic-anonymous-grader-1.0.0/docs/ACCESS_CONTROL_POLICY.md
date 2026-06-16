# Academic Anonymous Grader — Access-Control Policy

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Approved
- **Last Updated:** 2026-06-16

## 1. Roles

### Administrator
Full system access except where limited below:
- Create, read, update, deactivate users.
- Assign roles to users.
- Create, update, archive materials and assessments.
- Manage academic structure (departments, stages, terms, academic years).
- Import student submissions with encrypted identity upload.
- Resolve identity-matching conflicts during import.
- Grade assigned assessments.
- Review and finalize assessments.
- Export identity-bearing result data.
- View audit logs.
- Manage backup creation, verification, and restore.
- Manage deployment settings.
- View all analytics.
- Must not create shared accounts.

### Grader (Instructor-equivalent role)
- View only assigned anonymous grading work.
- Grade and provide feedback.
- Complete assigned grading.
- Correct returned work.
- View own grading progress.
- View scoped analytics (own assigned assessments only).
- Never views or accesses student identity information.
- Cannot manage users, imports, finalization, exports, backups, or academic structure.

### Reviewer
- View finalization-ready assessments.
- Approve or return assessments for correction.
- Cannot modify grades.
- Cannot access identities.
- Cannot import or export.

### Viewer
- Read-only access to approved materials and results.
- View analytics.
- Cannot modify any data.
- Cannot access identities.

### Exporter
- Can trigger identity-bearing exports.
- Cannot modify system data.
- Cannot access identity directly (export only).

### Legacy Roles
Legacy roles may exist from previous versions for compatibility. They grant no operational permissions and should be migrated to the current role model.

## 2. Least-Privilege Principle
Each user should be assigned only the roles necessary for their responsibilities. Granting Administrator access to non-administrative users should be avoided.

## 3. Account Management

### Account Creation
- Users are created by an Administrator.
- Each account requires a unique username and strong password.
- Initial passwords must be changed on first login (handled by the application).

### Account Review
- User accounts should be reviewed every 90 days.
- Inactive accounts (no login for 90 days) should be flagged for review.
- Accounts for users who have left the institution should be deactivated promptly.

### Inactive Account Handling
- Accounts inactive for >90 days: flag for Administrator review.
- Accounts inactive for >180 days: deactivate after confirmation.
- Deactivated accounts can be reactivated by an Administrator.

### Password Reset
- Passwords are hashed using bcrypt and stored securely.
- An Administrator can reset a user's password.
- The application does not email passwords or reveal existing hashes.

### Last-Active-Administrator Protection
- The system prevents an Administrator from being the last active Administrator when attempting user deletion or role change.
- This prevents accidental lockout.

### Temporary Access
- Temporary accounts should have a documented end date.
- The Administrator should deactivate temporary accounts when access is no longer required.

### Role-Change Approval
- Role changes should be approved by the Institutional System Owner or designee.
- The change is recorded in the audit log.

### Termination / Offboarding
1. Deactivate the user account immediately.
2. The user's contributions (grades, feedback) remain in the system.
3. Reassign any in-progress grading to another grader.
4. Document the deactivation.
