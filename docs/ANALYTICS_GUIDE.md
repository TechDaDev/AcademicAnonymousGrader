# Academic Anonymous Grader — Analytics Guide

## Overview

Phase 12 introduces privacy-safe analytics and reporting for **administrators** and **instructors** (graders). All analytics are computed from existing database records — no new data storage is required.

## Role Access

| Feature | Administrator | Instructor (Grader) |
|---|---|---|
| Overview Dashboard | All metrics | Own metrics only |
| Grading Progress | All assessments | Assigned assessments only |
| Instructor Workload | All instructors | Own workload only |
| Assessment Performance | All assessments | Assigned assessments only |
| Question Analysis | All questions | Assigned assessment questions |
| Grade Distribution | All assessments | Assigned assessments only |
| Correction Analytics | All assessments | Assigned assessments only |
| Finalization Readiness | All assessments | Not available |
| Data Quality Report | Full report | Not available |
| Export Reports | All reports | If enabled by administrator |

## Tab Reference

### Administrator Tabs

1. **Overview** — Dashboard cards with system-wide metrics: materials, assessments, submissions, completion rates, turnaround times, and finalization readiness counts.
2. **Grading Progress** — Detailed breakdown of grading statuses across assessments with claim tracking and turnaround time averages.
3. **Instructor Workload** — Comparison table showing all instructors' assignment counts, completion percentages, and workload status labels (light/balanced/high/overloaded).
4. **Assessment Performance** — Per-assessment statistics: mean, median, min, max, standard deviation, quartiles, pass/fail rates.
5. **Question Analysis** — Per-question metrics: difficulty index, score distribution, flag detection.
6. **Grade Distribution** — Grade bands (90–100%, 80–89%, etc.) with counts and percentages, plus Q1/Q3 summary.
7. **Corrections** — Correction cycle analytics: returned, resolved, unresolved, turnaround time.
8. **Finalization Readiness** — Per-assessment readiness status with blocker reason codes.
9. **Data Quality** — Automated data quality checks with severity levels (critical/warning/info).
10. **Export Reports** — Generate privacy-safe XLSX reports.

### Instructor Tabs

1. **My Overview** — Personal metrics: assigned assessments, pending/completed submissions, corrections, turnaround.
2. **My Progress** — Grading progress for assigned assessments only.
3. **My Workload** — Personal workload metrics and status.
4. **Assessment Performance** — Performance for actively assigned assessments.
5. **Question Analysis** — Question-level analytics for assigned assessments.
6. **Corrections** — Correction analytics for assigned assessments.

## Metrics Definitions

### Grading Statuses

| Status | Definition |
|---|---|
| Not Started | Pending, no grader assigned |
| Claimed | Grader assigned but not yet started |
| Draft | Grader working (in_progress) |
| Completed | Fully graded (graded) |
| Needs Correction | Returned by reviewer |
| Corrected | Re-graded after correction |
| Approved | Reviewed and approved |
| Finalized | Assessment finalized |

### Difficulty Index

```
difficulty_index = mean_awarded_grade / maximum_grade
```

Interpretation:
- **0.0–0.3**: Difficult
- **0.3–0.7**: Moderate
- **0.7–1.0**: Easy

**Limitations**: Difficulty index is a descriptive statistic only. It does not constitute psychometric validation, especially for small sample sizes.

### Workload Status

- **Light**: Few assignments, low pending ratio
- **Balanced**: Moderate workload
- **High**: Significant pending work
- **Overloaded**: Very high pending ratio

These labels are **advisory only** and should not be used for punitive evaluation.

## Privacy Thresholds

The minimum group size (default: 5, minimum: 3) controls when detailed statistics are shown. Groups below the threshold have their statistics suppressed:
- Mean, median, min, max, standard deviation suppressed
- Grade bands hidden
- Export reports exclude suppressed metrics

## Turnaround Time Calculations

| Metric | Calculation |
|---|---|
| Claim → Completion | `completed_at - grading_claimed_at` |
| Return → Correction | `reviewed_at - completed_at` (approximate) |
| Import → First Grading | Not calculated in Phase 12 |

All calculations use UTC. Negative durations are ignored.

## Known Limitations

- Analytics are **descriptive**, not prescriptive
- Instructor comparisons require context — raw averages may not account for different assessment difficulties
- Question difficulty is not proof of question quality
- Small group values may be suppressed
- No student identity is available in analytics
- Discrimination analysis requires a minimum sample size
