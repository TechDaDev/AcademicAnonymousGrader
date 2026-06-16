# Academic Anonymous Grader — UI Requirements

## Technology

- **Framework:** Streamlit
- **Initial theme:** Streamlit default light theme (custom theming to be defined in Phase 1)
- **Layout:** Wide layout (`st.set_page_config(layout="wide")`)

## Page Structure

### Dashboard

| Aspect | Detail |
|--------|--------|
| **Purpose** | Overview of all materials and assessments; quick access to common actions. |
| **Displayed information** | List of materials with assessment counts; summary statistics (total students, graded vs. ungraded). |
| **Inputs** | None (navigation only). |
| **Actions** | Navigate to Materials, Assessments, Import, Grading, Review, Export pages. |
| **Validation messages** | None. |
| **Empty state** | "No materials yet. Create your first material." with a button to the Materials page. |
| **Error state** | Database connection error: "Unable to connect to the database." with troubleshooting tips. |
| **Privacy restrictions** | No student identity data shown. Aggregate counts only. |

### Materials

| Aspect | Detail |
|--------|--------|
| **Purpose** | Manage academic materials (courses/subjects). |
| **Displayed information** | List of materials with name, code, creation date, assessment count. |
| **Inputs** | Material name (text), optional code (text), optional description (text area). |
| **Actions** | Create material, select material (navigates to its assessments), edit name/code, delete (if no assessments exist). |
| **Validation messages** | "Material name is required." / "Material name must be unique." |
| **Empty state** | "No materials. Create one to get started." |
| **Error state** | "Failed to create material. Please try again." |
| **Privacy restrictions** | No student data displayed. |

### Assessments

| Aspect | Detail |
|--------|--------|
| **Purpose** | Manage assessments within a selected material. |
| **Displayed information** | List of assessments with name, max grade, question count, status, completion percentage. |
| **Inputs** | Assessment name (text), max grade (number), optional description (text area). |
| **Actions** | Create assessment, select assessment, edit settings, delete (if no submissions), manage questions, navigate to Import/Grading/Review/Export. |
| **Validation messages** | "Assessment name is required." / "Max grade must be a positive number." |
| **Empty state** | "No assessments yet. Create your first assessment for this material." |
| **Error state** | "Failed to load assessments. Check database connection." |
| **Privacy restrictions** | No student data displayed. |

**Question configuration (sub-page or expander):**
- Table of questions: Number, Title, Max Mark
- Add question button, remove question button
- Validation: "Sum of question marks must equal assessment max grade."

### Import

| Aspect | Detail |
|--------|--------|
| **Purpose** | Upload and preview assessment response files. |
| **Displayed information** | File upload widget, detected columns table (name, normalised name, classification), preview of first 10 rows, identity-matching results, validation results. |
| **Inputs** | File upload (`.html` only); identity resolution dropdowns when matches are ambiguous. |
| **Actions** | Upload file, confirm/reject column mapping, resolve ambiguous identity matches manually, confirm import, cancel. |
| **Validation messages** | See file validation rules (F001–F010, S007–S015). |
| **Empty state** | "Select an assessment first, then upload a response file." |
| **Error state** | "Unable to parse the file. The file may be invalid or corrupted." / "Ambiguous identity matches must be resolved before import can proceed." |
| **Privacy restrictions** | Raw student data is visible in the preview table. This is the **only page** where identities are shown. A note at the top warns: "This preview shows real student data. After import, identities will be hidden during grading." |

### Grading

| Aspect | Detail |
|--------|--------|
| **Purpose** | Grade student responses anonymously. |
| **Displayed information** | Material name, assessment name, anonymous student ID, question number and title, maximum mark, student response (in a monospaced, scrollable area), score input, feedback input, progress (e.g., "5/30 graded"), save status indicator. |
| **Inputs** | Score (numeric), feedback (text area, optional). |
| **Actions** | Save, Save and Next, Previous, Skip, Mark for Review. |
| **Validation messages** | "Score must be between 0 and [max_mark]." / "Score is required." |
| **Empty state** | "No responses to grade. Import a response file first." |
| **Error state** | "Failed to save grade. Please try again." with retry button. |
| **Privacy restrictions** | **Never display first name, last name, or email.** Only the anonymous ID is shown. A persistent banner at the top reinforces: "Grading anonymously — student identities are hidden." |

**Grading page layout (conceptual):**

```
┌────────────────────────────────────────────────────┐
│  Material: DBOAIC1101 — OOP                        │
│  Assessment: Midterm Exam                    [5/30]│
│                                                    │
│  ┌─ Anonymous ID: A3F9K2B1 ──────────── [Skip] ─┐ │
│  │                                                │ │
│  │  Question 2: Explain polymorphism  (Max: 5)     │ │
│  │                                                │ │
│  │  ┌─ Response ──────────────────────────────┐   │ │
│  │  │ Polymorphism is the ability of an        │   │ │
│  │  │ object to take many forms. In Java,      │   │ │
│  │  │ this is achieved through method          │   │ │
│  │  │ overloading and overriding.              │   │ │
│  │  │                                            │   │ │
│  │  │ Example:                                   │   │ │
│  │  │   class Animal {                           │   │ │
│  │  │     void sound() {                         │   │ │
│  │  │       System.out.println("...");           │   │ │
│  │  │     }                                      │   │ │
│  │  │   }                                        │   │ │
│  │  └────────────────────────────────────────┘   │ │
│  │                                                │ │
│  │  Score:  [4.00]  /  5.00                       │ │
│  │  Feedback (optional):                          │ │
│  │  ┌────────────────────────────────────────┐   │ │
│  │  │ Good explanation, but could include    │   │ │
│  │  │ more detail about compile-time vs      │   │ │
│  │  │ runtime polymorphism.                  │   │ │
│  │  └────────────────────────────────────────┘   │ │
│  │                                                │ │
│  │  [Save]  [Save & Next]  [Previous]  [Flag]    │ │
│  │                                                │ │
│  │  ✓ Saved  |  Score: 4.00 / 5.00               │ │
│  └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

### Review

| Aspect | Detail |
|--------|--------|
| **Purpose** | Review grading progress, find incomplete or flagged responses. |
| **Displayed information** | Table of all submissions with: anonymous ID, question-level scores, total, completion status (complete/incomplete), review flag. |
| **Inputs** | Filter dropdowns (status: all/incomplete/complete; flag: all/flagged; score: all/zero/unmarked). |
| **Actions** | Click a row to navigate to that response on the Grading page. |
| **Validation messages** | None (review only). |
| **Empty state** | "No submissions to review. Import a response file first." |
| **Error state** | "Failed to load review data." |
| **Privacy restrictions** | Only anonymous IDs shown. No names or emails. |

**Review table columns:**
1. Anonymous ID
2. Q1 Score / Max
3. Q2 Score / Max
4. …QN Score / Max
5. Total Score
6. Status (Complete / Incomplete)
7. Review Flag (Yes / No)
8. Action (Link to Grading page)

### Export / Finalize

| Aspect | Detail |
|--------|--------|
| **Purpose** | Finalize assessment grades and generate an authorised Excel report with restored identities. |
| **Workflow** | (1) Select material → (2) Select assessment → (3) View finalization readiness → (4) Confirm checkbox → (5) Finalize → (6) Generate workbook → (7) Download or re-export. |
| **Displayed information** | Total submissions, approved submissions, readiness (pass/fail), blocking errors (FA001–FA013) with codes, warnings, assessment maximum grade, final grade total, average/min/max grades, export reference, row count, file size, SHA-256 hash prefix, export history. |
| **Inputs** | Assessment selector, confirmation checkbox ("I confirm that all grades and reviews are complete and that finalization will lock grading changes."), Finalize button, Generate Workbook button, Download button. |
| **Actions** | Run readiness validation, check confirmation, finalize assessment, generate workbook, download Excel file, re-export. |
| **Validation messages** | See finalization rules FA001–FA013 and export rules E001–E008. |
| **Empty state** | "No reviewable assessments found for this material." / "Assessment is not finalized yet." |
| **Error state** | "Assessment is not ready for finalization." with blocking-error list. "Export failed." with details. "Workbook generation failed." with details. |
| **Privacy restrictions** | **No identities displayed in the browser.** Identities are decrypted only during workbook generation. Confirmation checkbox required before finalization. Generated filename uses `final_grades_{id}.xlsx` — no student names. |
| **Export history** | Each export creates an `ExportRecord` with export reference, timestamp, row count, file size, and SHA-256 hash prefix. Re-export is allowed and creates a new record without modifying grades or finalization state. |

### Settings

| Aspect | Detail |
|--------|--------|
| **Purpose** | Configure application settings and perform maintenance. |
| **Displayed information** | Current settings, database path, backup status. |
| **Inputs** | Database backup path (text), backup button. |


---

## Authorization Model

### Page Access Matrix

| Page | Administrator | Instructor |
|------|:---:|:---:|
| Dashboard | ✅ | ✅ |
| Materials | ✅ | ❌ |
| Assessments | ✅ | ❌ |
| Import | ✅ | ❌ |
| Grading | ✅ | ✅ |
| Review | ✅ | ❌ |
| Export | ✅ | ❌ |
| Users | ✅ | ❌ |
| Audit | ✅ | ❌ |
| Backup | ✅ | ❌ |
| Settings | ✅ | ❌ |

### Operational Roles

- **Administrator** (`administrator`): Full access — materials, assessments, questions, import, grading, review, finalization, export (with identity restoration), users, audit, backup, restore, settings.
- **Instructor** (`grader`, displayed as Instructor): Anonymous grading only. Views anonymous submissions, enters grades and feedback, saves drafts, marks grading complete, corrects returned submissions. Never sees student identity.

### Legacy Roles

`reviewer`, `exporter`, and `viewer` are legacy. Not assignable to new users. No operational permissions.

### Navigation

- **Administrator sidebar**: Dashboard, Materials, Assessments, Import, Grading, Review, Export, Users, Audit, Backup, Settings, Logout.
- **Instructor sidebar**: Dashboard, Grading, Logout. Hidden links for unauthorized pages are not rendered. Unauthorized direct URLs are blocked with `require_page_access_safe()` showing a safe error message.
- **Sidebar rendering**: The sidebar is rendered by `app.py` using `st.sidebar.markdown` links. The default Streamlit page navigation is hidden via CSS. Role-aware `can_access_page()` determines which links are visible for each role.
| **Actions** | Back up database, view audit log (future), configure identity encryption (future). |
| **Validation messages** | "Backup path is invalid." / "Backup created successfully." |
| **Empty state** | N/A (settings always have defaults). |
| **Error state** | "Failed to create backup. Check disk space and permissions." |
| **Privacy restrictions** | Settings page may show database location; no student data displayed. |

## Accessibility Considerations

- All interactive elements must have accessible labels.
- Colour alone must not be used to convey status (use icons or text in addition).
- Keyboard navigation must work for all grading actions.
- Error messages must be clear and actionable.
- Streamlit's built-in accessibility features should be leveraged.

## Arabic Text Considerations

- Response text containing Arabic characters must be preserved and displayed correctly.
- The system should handle right-to-left (RTL) content within response display areas.
- Monospaced fonts may not render Arabic ideally; the display should use a font that supports Arabic script for text-based responses.
- Feedback and scores are entered in English/Latin script (lecturer's language).
- Sorting by student name must handle Arabic names correctly if sorting is implemented.

## Responsive Considerations

- The primary target is a desktop/laptop screen (minimum 1280×720 recommended).
- The grading page is designed for a single-column layout on narrower screens.
- Tables should scroll horizontally on narrow screens.
