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
