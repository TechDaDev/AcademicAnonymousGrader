# Academic Anonymous Grader — Data Model

## Design Principles

1. **Identity separation:** Student identity data is stored in tables separate from grading data. The grading interface queries only tables without personally identifiable information (PII).
2. **Random anonymous IDs:** Anonymous IDs are generated using cryptographically secure randomness. They are never derived from names, email addresses, or student numbers.
3. **Immutable finalised grades:** Once an assessment is finalised, grade records become read-only unless the assessment is formally reopened (an audited action).
4. **Import audit trail:** Every file import creates an ImportBatch record. Reimports are tracked, and deduplication logic prevents silent duplication.
5. **Traceability:** Every significant action (import, grade save, finalisation, export, reopen) is recorded in the audit log.
6. **Keyed identity fingerprint:** Identity fingerprints use HMAC-SHA256 with a dedicated `IDENTITY_FINGERPRINT_KEY` separate from the identity encryption key. Fingerprints are matching aids, not primary keys.
7. **Hierarchical identity matching:** Students are matched across imports using a priority order: institutional student ID, then normalised email, then keyed fingerprint, then manual resolution. Names alone never trigger automatic merging. Ambiguous matches block import and require lecturer review.

---

## Entity Relationship Diagram (Text)

```
 ┌──────────────┐       ┌──────────────┐
 │   Lecturer   │       │   Material   │
 │   (User)     │──1:N──│              │
 └──────────────┘       └──────────────┘
                               │
                             1:N
                               │
                               ▼
                        ┌──────────────┐       ┌──────────────┐
                        │  Assessment  │──1:N──│   Question   │
                        └──────────────┘       └──────────────┘
                               │
                             1:N
                               │
                               ▼
 ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
 │  Student     │       │  Submission  │──1:N──│   Response   │
 │  Identity    │──1:N──│              │       │              │
 └──────────────┘       └──────────────┘       └──────────────┘
        │                      │                       │
        │                      │                       │
        │                      │                      1:1
        │                      │                       │
        │                      │                       ▼
        │                      │                ┌──────────────┐
        │                      │                │GradeRecord   │
        │                      │                │              │
        │                      │                └──────────────┘
        │                      │
        │               ┌──────────────┐
        │               │ ImportBatch  │
        │               └──────────────┘
        │
        ▼
 ┌──────────────┐
 │Anonymous     │
 │Student       │──1:1── StudentIdentity
 └──────────────┘

 ┌──────────────┐       ┌──────────────┐
 │ AuditEvent   │       │ ExportRecord │
 └──────────────┘       └──────────────┘
```

### Relationship Summary

- **Lecturer 1:N Material** — A lecturer can create multiple materials.
- **Material 1:N Assessment** — A material contains multiple assessments.
- **Assessment 1:N Question** — An assessment defines multiple questions.
- **Assessment 1:N Submission** — An assessment receives multiple student submissions.
- **StudentIdentity 1:N Submission** — A student can submit to multiple assessments.
- **StudentIdentity 1:1 AnonymousStudent** — Each identity has exactly one anonymous ID.
- **Submission 1:N Response** — A submission has one response per question.
- **Response 1:1 GradeRecord** — Each response receives exactly one grade record.
- **ImportBatch 1:N Submission** — An import batch creates multiple submissions.
- **Assessment 1:N ImportBatch** — An assessment can be imported multiple times.

---

## Entities

### Lecturer (User)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Represents the lecturer using the system. |
| **Suggested fields** | `id`, `username`, `password_hash`, `display_name`, `created_at`, `last_login` |
| **Required fields** | `username`, `password_hash` |
| **Optional fields** | `display_name`, `last_login` |
| **Relationships** | Has many `Material` records. |
| **Uniqueness** | `username` must be unique. |
| **Lifecycle** | Created on first setup. Retained indefinitely. |
| **Contains PII?** | Yes (`username`, `display_name`). |

### Material

| Aspect | Detail |
|--------|--------|
| **Purpose** | Represents an academic course or subject. |
| **Suggested fields** | `id`, `lecturer_id`, `name`, `code`, `description`, `created_at`, `updated_at` |
| **Required fields** | `lecturer_id`, `name` |
| **Optional fields** | `code`, `description` |
| **Relationships** | Belongs to a `Lecturer`; has many `Assessment` records. |
| **Uniqueness** | `name` is unique per lecturer (or `name` + `code` combination). |
| **Lifecycle** | Created by lecturer. Retained until explicitly deleted (with cascade). |
| **Contains PII?** | No. |

### Assessment

| Aspect | Detail |
|--------|--------|
| **Purpose** | Represents a graded component within a material. |
| **Suggested fields** | `id`, `material_id`, `title`, `assessment_type`, `academic_year`, `maximum_grade`, `status` (draft/ready/grading/finalized), `finalized_at`, `finalization_status` (not_ready/ready_to_finalize/finalized), `finalization_note`, `created_at`, `updated_at` |
| **Required fields** | `material_id`, `title`, `maximum_grade` |
| **Optional fields** | `assessment_type`, `academic_year`, `finalized_at`, `finalization_note` |
| **Relationships** | Belongs to a `Material`; has many `Question`, `Submission`, `ImportBatch`, and `ExportRecord` records. |
| **Lifecycle** | Draft → Ready → Grading → Finalized. `finalization_status` tracks readiness for finalization. After finalization, grading, review, and import are blocked. |
| **Contains PII?** | No. |

### Question

| Aspect | Detail |
|--------|--------|
| **Purpose** | Represents a single question within an assessment. |
| **Suggested fields** | `id`, `assessment_id`, `number`, `title`, `max_mark`, `created_at` |
| **Required fields** | `assessment_id`, `number`, `max_mark` |
| **Optional fields** | `title` |
| **Relationships** | Belongs to an `Assessment`; has many `Response` records. |
| **Uniqueness** | `number` is unique within an assessment. |
| **Lifecycle** | Created when assessment is configured. Cannot be deleted after import without caution. |
| **Contains PII?** | No. |

### StudentIdentity

| Aspect | Detail |
|--------|--------|
| **Purpose** | Stores real student identifying information. Separated from grading data. Uses an internally generated UUID as the primary key. |
| **Suggested fields** | `id` (UUID, primary key), `institutional_student_id`, `first_name` (encrypted), `last_name` (encrypted), `email` (encrypted), `identity_fingerprint` (HMAC-SHA256, keyed), `created_at`, `updated_at` |
| **Required fields** | `first_name` |
| **Optional fields** | `last_name`, `email`, `institutional_student_id`, `identity_fingerprint` |
| **Relationships** | Has one `AnonymousStudent`; has many `Submission` records. |
| **Uniqueness** | `id` (UUID) is the primary key. `institutional_student_id` should be unique when present. `email` is not a unique constraint; duplicate emails may exist due to source data errors. |
| **Lifecycle** | Created on first import. Updated on reimport if identity data changes. Never deleted in normal operation. Ambiguous matches block import and require lecturer review. |
| **Contains PII?** | **Yes.** This table contains personally identifiable information. All PII fields (first_name, last_name, email, institutional_student_id) are encrypted at rest in Phase 4. |

### AnonymousStudent

| Aspect | Detail |
|--------|--------|
| **Purpose** | Stores the mapping between a student and their anonymous grading ID. |
| **Suggested fields** | `id`, `student_identity_id`, `anonymous_id` (format: `STU-XXXXXXXX`), `created_at` |
| **Required fields** | `student_identity_id`, `anonymous_id` |
| **Optional fields** | None |
| **Relationships** | Belongs to exactly one `StudentIdentity`. |
| **Uniqueness** | `anonymous_id` has a database uniqueness constraint. `student_identity_id` must be unique (1:1 relationship). |
| **Lifecycle** | Created alongside `StudentIdentity`. Anonymous IDs are stable per student within the local system. The same student reimported for the same assessment receives the same anonymous ID. Cross-assessment unlinkability may be strengthened in a future phase, but initially one stable ID per student is preferred. |
| **Contains PII?** | No (the `anonymous_id` is random and contains no identity information). However, the foreign key links to PII. |
| **Generation rules** | Format `STU-XXXXXXXX` where `XXXXXXXX` is a cryptographically secure random alphanumeric string (e.g., `STU-7K4M9X2Q`). Generated using `secrets.token_hex()` or `secrets.token_urlsafe()`. Not derived from names, email addresses, student numbers, or response content. Collisions are checked on insertion; if a collision occurs the ID is regenerated. |

### ImportBatch

| Aspect | Detail |
|--------|--------|
| **Purpose** | Records metadata about a file import operation. Enables reimport tracking and deduplication. |
| **Suggested fields** | `id`, `assessment_id`, `filename`, `file_hash`, `row_count`, `column_count`, `imported_at`, `status` (pending/completed/failed/rolled_back) |
| **Required fields** | `assessment_id`, `filename`, `file_hash`, `row_count`, `column_count` |
| **Optional fields** | `error_message` |
| **Relationships** | Belongs to an `Assessment`; has many `Submission` records. |
| **Uniqueness** | No uniqueness constraint beyond `id`. Multiple batches per assessment are allowed. |
| **Lifecycle** | Created on import start. Updated on completion or failure. |
| **Contains PII?** | No (may contain filenames that include course codes, but not student PII). |

### Submission

| Aspect | Detail |
|--------|--------|
| **Purpose** | Represents a single student's submitted work for one assessment. |
| **Suggested fields** | `id`, `assessment_id`, `student_identity_id`, `import_batch_id`, `status` (started/completed), `started_at`, `completed_at`, `duration_seconds`, `source_grade`, `created_at`, `grading_status`, `review_status` (not_ready/ready_for_review/needs_correction/approved), `reviewed_at`, `review_note` |
| **Required fields** | `assessment_id`, `student_identity_id`, `import_batch_id` |
| **Optional fields** | `status`, `started_at`, `completed_at`, `duration_seconds`, `source_grade`, `reviewed_at`, `review_note` |
| **Relationships** | Belongs to an `Assessment` and a `StudentIdentity`; belongs to an `ImportBatch`; has many `Response` and `GradeRecord` records. |
| **Uniqueness** | `(assessment_id, student_identity_id)` must be unique — one submission per student per assessment. |
| **Lifecycle** | Created on import. Updated on reimport (response content). Never deleted in normal operation. `review_status` transitions through lifecycle. |
| **Contains PII?** | Indirectly, via `student_identity_id`. |

### Response

| Aspect | Detail |
|--------|--------|
| **Purpose** | Stores a student's answer to a single question. |
| **Suggested fields** | `id`, `submission_id`, `question_id`, `response_text`, `created_at`, `updated_at` |
| **Required fields** | `submission_id`, `question_id` |
| **Optional fields** | `response_text` (may be blank if student left the answer empty) |
| **Relationships** | Belongs to a `Submission` and a `Question`; has one `GradeRecord`. |
| **Uniqueness** | `(submission_id, question_id)` must be unique. |
| **Lifecycle** | Created on import. Updated on reimport. Retained even if blank. |
| **Contains PII?** | Potentially (student answers may contain self-identifying information). The grading interface does not display real names, but the response text itself is not PII by default. |

### GradeRecord

| Aspect | Detail |
|--------|--------|
| **Purpose** | Stores the score and feedback assigned by the lecturer to a single response. |
| **Suggested fields** | `id`, `response_id`, `score`, `feedback`, `graded_by` (lecturer_id), `graded_at`, `updated_at`, `is_finalised` (boolean, derived from assessment status) |
| **Required fields** | `response_id` |
| **Optional fields** | `score` (null until graded), `feedback`, `graded_at` |
| **Relationships** | Belongs to exactly one `Response`. |
| **Uniqueness** | `response_id` must be unique (1:1 with Response). |
| **Lifecycle** | Created when the first grade is saved. Updated on regrading. Made effectively read-only when assessment is finalised. |
| **Contains PII?** | No (feedback is tied to anonymous grading). Feedback text should not contain student identity. |

### AuditEvent

| Aspect | Detail |
|--------|--------|
| **Purpose** | Logs significant actions for traceability and accountability. |
| **Suggested fields** | `id`, `lecturer_id`, `event_type`, `description`, `assessment_id`, `material_id`, `timestamp`, `ip_address` (local), `metadata` (JSON) |
| **Required fields** | `lecturer_id`, `event_type`, `description` |
| **Optional fields** | `assessment_id`, `material_id`, `metadata` |
| **Relationships** | References `Lecturer`, optionally `Assessment` and `Material`. |
| **Uniqueness** | None (sequential log). |
| **Lifecycle** | Append-only. Never deleted. |
| **Contains PII?** | Should not contain student PII per privacy rules. May contain lecturer identity. |

### ExportRecord

| Aspect | Detail |
|--------|--------|
| **Purpose** | Records each authorised export of identifiable results. |
| **Suggested fields** | `id`, `assessment_id`, `export_format` (xlsx), `export_reference` (EXP-XXXXXXXX), `workbook_schema_version`, `file_name`, `file_hash` (SHA-256), `file_size`, `row_count`, `exported_at`, `created_at`, `updated_at` |
| **Required fields** | `assessment_id`, `file_name` |
| **Optional fields** | `file_hash`, `file_size`, `row_count`, `exported_at` |
| **Relationships** | Belongs to an `Assessment`. |
| **Security** | Never stores workbook bytes, decrypted identity data, or export file paths containing identity information. Each row is a metadata-only record. |
| **Uniqueness** | None — multiple exports per finalized assessment allowed. |
| **Lifecycle** | Created on each export. Retained indefinitely. Re-export does not modify existing records. |
