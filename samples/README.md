# Local Sample Files — Manual Testing Only

This folder is for **local manual testing only**.

## Policy

- **Files in this directory may contain sensitive academic data** including real student names, email addresses, institutional IDs, grades, and responses.
- **Do not commit** any sample file that contains real or realistic personal data.
- For **committed, synthetic test data**, use `tests/fixtures/` instead.
- **Remove or anonymize** all local sample files before sharing or archiving the repository.

## How to Use

1. Place exported LMS response HTML files here for manual testing.
2. Open the Streamlit app and upload from this folder.
3. After testing, delete or anonymize the files.
4. Never copy content from `samples/` into `tests/fixtures/`.

## What Gets Committed

Only this README and `.gitkeep` are tracked.
All other files in this folder are ignored per `.gitignore`.
