# Academic Anonymous Grader — Reporting Privacy

## Core Privacy Principles

1. **Aggregate Only** — Analytics use anonymous or aggregate academic data. Real student identity appears only in the existing authorized identity-bearing final export workflow.
2. **No Identity in Analytics** — The analytics layer never queries `StudentIdentity` or decrypts ciphertext. All analytics operate on `AnonymousStudent`, `Submission`, `GradeRecord`, and similar aggregate models.
3. **Privacy Thresholds** — A minimum group size (default: 5, minimum: 3) prevents re-identification from small-group statistics.
4. **Suppression** — When a group falls below the threshold, detailed statistics are suppressed and exports exclude suppressed values.

## Data Never Exposed in Analytics

The following are **never** available through analytics:

- Real student names
- Email addresses
- Institutional student IDs
- Identity UUIDs
- Ciphertext values
- Fingerprints
- Raw student responses
- Grader feedback text
- Individual grade rows (disguised as analytics)
- Decrypted identity data

## Authorization Enforcement

Every analytics service function:
1. Requires an `AuthContext`
2. Checks for the `view_analytics` permission
3. Scopes results to authorized assessments
4. Returns generic privacy-safe errors for unauthorized requests

### Administrator Scope
- Sees all materials and assessments
- Views all instructor workload summaries
- Exports all report types

### Instructor Scope
- Sees only actively assigned assessments
- Views only own workload
- Cannot access another instructor's private data
- Cannot request unassigned assessment analytics
- Generic errors prevent ID enumeration

### Legacy Roles
- `reviewer`, `exporter`, `viewer` — no analytics permissions
- Unauthenticated users — blocked entirely

## Suppression Rules

1. Groups below `ANALYTICS_MINIMUM_GROUP_SIZE`:
   - Mean, median, min, max, standard deviation → `None`
   - Grade bands → empty list
   - Pass/fail counts → 0
   - Exports → suppressed values absent
2. Filters that would reduce a report below threshold → suppression triggered
3. Suppressed values never appear in tooltips, exports, logs, or API objects
4. Charts display empty state instead of suppressed data

## Caching Safety

If Streamlit caching is used:
- Only anonymous aggregate results are cached
- Authorization scope is included in cache keys
- Filter values are included in cache keys
- Cache is invalidated after grading, assignment, review, finalization, import, restore, or migration changes
- AuthContext objects are never cached
- Decrypted identities are never cached
- Administrator results never leak to Instructor sessions

## Audit Events

Analytics audit events contain:
- Report type
- Material/assessment ID
- Instructor user ID (where authorized)
- Date range
- Status filters
- Suppression applied
- Export format

Audit events **never** contain:
- Names, emails, IDs
- Response text
- Feedback
- Individual grades
- Grade distributions that could identify a student
- Exported workbook bytes

## Export Privacy

XLSX reports:
- No identity columns
- No response or feedback text
- No hidden identity sheets
- No formulas that expose hidden data
- No external links
- No macros
- Suppressed values absent
- Generated in memory — no plaintext temporary files
- Privacy-safe filenames
- Report metadata includes generation timestamp, filter summary, and suppression notes
