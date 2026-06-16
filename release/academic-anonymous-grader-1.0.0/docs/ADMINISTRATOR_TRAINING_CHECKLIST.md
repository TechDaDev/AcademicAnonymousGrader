# Academic Anonymous Grader — Administrator Training Checklist

## Version and Status
- **Document Version:** 1.0.0
- **Status:** Ready for Training
- **Last Updated:** 2026-06-16

## Instructions
This checklist should be completed by new Administrators during onboarding. Each item should be demonstrated and signed off by a trainer.

## Prerequisites
- [ ] Application is installed and running.
- [ ] Trainer has Administrative access.
- [ ] Trainee has a temporary Administrator account.

## Training Items

### 1. Login
- [ ] Navigate to the application URL.
- [ ] Enter credentials.
- [ ] Confirm Dashboard loads.
- [ ] Verify displayed version is 1.0.0.
- [ ] Logout.
- [ ] Confirm failed login displays error (wrong password).

### 2. User Creation
- [ ] Navigate to Users page.
- [ ] Create a new user with role Grader.
- [ ] Create a new user with role Viewer.
- [ ] Verify new users appear in the user list.
- [ ] Attempt to create a duplicate username — confirm rejection.

### 3. Instructor (Grader) Assignment
- [ ] Navigate to Instructor Assignments.
- [ ] Select an assessment.
- [ ] Assign a Grader to the assessment.
- [ ] Verify the assignment appears.

### 4. Academic Structure
- [ ] Navigate to Academic Structure.
- [ ] View existing Departments (3 default), Stages (4), Terms (2).
- [ ] Create a new Academic Year.
- [ ] Modify a stage display name.

### 5. Material and Assessment Creation
- [ ] Navigate to Materials.
- [ ] Create a new Material.
- [ ] Navigate to Assessments.
- [ ] Create a new Assessment under the Material.
- [ ] Add questions to the Assessment.

### 6. Secure Import
- [ ] Navigate to Import.
- [ ] Upload a sample CSV file.
- [ ] Map columns to identity and response fields.
- [ ] Review the dry-run preview.
- [ ] Execute the import.
- [ ] Verify import results.

### 7. Identity Resolution
- [ ] If import finds ambiguous matches, demonstrate the resolution interface.
- [ ] Show manual match, create-new, and skip decisions.

### 8. Anonymous Grading Oversight
- [ ] Verify that grading progress can be monitored.
- [ ] Confirm no identities are visible during grading.

### 9. Review
- [ ] Navigate to Review.
- [ ] View grading completeness.
- [ ] Return incomplete submissions for correction.

### 10. Finalization
- [ ] Verify all conditions are met before finalization.
- [ ] Finalize an assessment.
- [ ] Confirm grades are locked.

### 11. Final Export
- [ ] Navigate to Export.
- [ ] Export anonymous results (de-identified).
- [ ] Export identity-bearing results.
- [ ] Verify the exported XLSX file.

### 12. Analytics
- [ ] Navigate to Analytics.
- [ ] View assessment overview.
- [ ] View question analysis.
- [ ] View distributions.
- [ ] Verify no identity data appears.

### 13. Audit
- [ ] Navigate to Audit.
- [ ] View recent events.
- [ ] Identify login, import, and export events.
- [ ] Filter by event type.

### 14. Backup
- [ ] Run a backup using the script.
- [ ] Verify the backup archive was created.

### 15. Restore
- [ ] Restore from a verified backup.
- [ ] Confirm data is restored.
- [ ] Confirm health passes.

### 16. Start/Stop/Status
- [ ] Run the status script.
- [ ] Stop the application.
- [ ] Verify the application is down.
- [ ] Start the application.
- [ ] Verify health.

### 17. Update
- [ ] Review the update procedure (documented, not performed during training).

### 18. Incident Escalation
- [ ] Review the Incident-Response Plan.
- [ ] Identify who to contact for key exposure.
- [ ] Identify who to contact for unauthorized access.

### 19. Key Handling
- [ ] Review the Key-Custody Policy.
- [ ] Understand where keys are stored.
- [ ] Understand prohibited storage locations.
- [ ] Understand consequences of lost keys.

## Sign-Off

| Item | Trainer Initials | Trainee Initials | Date |
|------|-----------------|------------------|------|
| Login | | | |
| User Creation | | | |
| Grader Assignment | | | |
| Academic Structure | | | |
| Material/Assessment | | | |
| Secure Import | | | |
| Identity Resolution | | | |
| Grading Oversight | | | |
| Review | | | |
| Finalization | | | |
| Final Export | | | |
| Analytics | | | |
| Audit | | | |
| Backup | | | |
| Restore | | | |
| Start/Stop/Status | | | |
| Update (review) | | | |
| Incident Escalation | | | |
| Key Handling | | | |

---
**Trainer Name:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Trainee Name:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
**Date Completed:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
