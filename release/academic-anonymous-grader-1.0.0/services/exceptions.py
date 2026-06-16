# Academic Anonymous Grader — Domain Exceptions
"""Typed service-layer exceptions for domain operations."""


class MaterialError(Exception):
    """Base exception for material operations."""


class MaterialNotFoundError(MaterialError):
    """Material does not exist."""


class DuplicateMaterialError(MaterialError):
    """A conflicting active material already exists."""


class MaterialValidationError(MaterialError):
    """Material data failed validation."""


class AssessmentError(Exception):
    """Base exception for assessment operations."""


class AssessmentNotFoundError(AssessmentError):
    """Assessment does not exist."""


class AssessmentValidationError(AssessmentError):
    """Assessment data failed validation."""


class InvalidAssessmentStateError(AssessmentError):
    """Assessment state transition is not allowed."""


class QuestionError(Exception):
    """Base exception for question operations."""


class QuestionNotFoundError(QuestionError):
    """Question does not exist."""


class QuestionValidationError(QuestionError):
    """Question data failed validation."""


class QuestionDeletionBlockedError(QuestionError):
    """Question cannot be deleted because responses exist."""


class GradingError(Exception):
    """Base exception for grading operations."""


class SubmissionNotFoundError(GradingError):
    """Submission does not exist."""


class GradingQuestionNotFoundError(GradingError):
    """Question does not exist in the assessment."""


class InvalidGradeError(GradingError):
    """Grade value is invalid (negative, above max, or wrong format)."""


class IncompleteGradingError(GradingError):
    """Not all questions have been graded."""


class GradeConflictError(GradingError):
    """Grade record already exists with conflicting data."""


class ReviewError(Exception):
    """Base exception for review operations."""


class ReviewSubmissionNotFoundError(ReviewError):
    """Review submission does not exist."""


class ReviewValidationError(ReviewError):
    """Submission does not meet review criteria."""


class ReviewApprovalBlockedError(ReviewError):
    """Submission cannot be approved due to unresolved issues."""


class ReviewNoteRequiredError(ReviewError):
    """Reviewer note is required for this action."""


class AssessmentReviewIncompleteError(ReviewError):
    """Assessment has unresolved review issues."""


class FinalizationError(Exception):
    """Base exception for finalization operations."""


class AssessmentNotReadyForFinalizationError(FinalizationError):
    """Assessment does not meet finalization criteria."""


class AssessmentAlreadyFinalizedError(FinalizationError):
    """Assessment is already finalized."""


class FinalizedAssessmentModificationError(FinalizationError):
    """Cannot modify a finalized assessment."""


class FinalizedAssessmentImportError(FinalizationError):
    """Cannot import into a finalized assessment."""


class FinalizedAssessmentExportError(FinalizationError):
    """Export failed for a finalized assessment."""


class ExportIdentityError(Exception):
    """Base exception for export identity operations."""


class ExportIdentityDecryptionError(ExportIdentityError):
    """Failed to decrypt identity for export."""


class ExportWorkbookError(Exception):
    """Base exception for workbook generation."""


class ExportValidationError(Exception):
    """Export data failed validation."""


class AuthenticationError(Exception):
    """Base exception for authentication operations."""


class InvalidCredentialsError(AuthenticationError):
    """Username or password is invalid."""


class AccountDisabledError(AuthenticationError):
    """User account is disabled."""


class AccountLockedError(AuthenticationError):
    """User account is temporarily locked."""


class DuplicateUsernameError(AuthenticationError):
    """A user with this username already exists."""


class UserNotFoundError(AuthenticationError):
    """User does not exist."""


class WeakPasswordError(AuthenticationError):
    """Password does not meet strength requirements."""


class AuthorizationError(Exception):
    """Base exception for authorization failures."""


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""


class AuditError(Exception):
    """Base exception for audit logging."""


class BackupError(Exception):
    """Base exception for backup operations."""


class BackupNotFoundError(BackupError):
    """Backup record does not exist."""


class BackupCorruptedError(BackupError):
    """Backup archive is corrupted or invalid."""


class BackupHashMismatchError(BackupError):
    """Backup hash does not match expected value."""


class BackupSchemaMismatchError(BackupError):
    """Backup schema version is incompatible."""


class AssignmentError(Exception):
    """Base exception for instructor assignment operations."""


class AssignmentNotFoundError(AssignmentError):
    """Assignment does not exist."""


class DuplicateAssignmentError(AssignmentError):
    """An active assignment already exists for this instructor and assessment."""


class AssignmentBlockedByFinalizationError(AssignmentError):
    """Cannot assign instructors to a finalized assessment."""


class InstructorAssignmentError(AssignmentError):
    """Target user is not a valid instructor for assignment."""


class GradingClaimError(Exception):
    """Base exception for grading claim operations."""


class GradingClaimConflictError(GradingClaimError):
    """Submission is already claimed by another instructor."""


class GradingClaimExpiredError(GradingClaimError):
    """Grading claim has expired and can be reclaimed."""


class GradingClaimNotFoundError(GradingClaimError):
    """No active grading claim exists for this submission."""


class RestoreError(Exception):
    """Base exception for restore operations."""


class RestoreValidationError(RestoreError):
    """Backup failed pre-restore validation."""


class RestoreFailedError(RestoreError):
    """Restore operation failed."""
