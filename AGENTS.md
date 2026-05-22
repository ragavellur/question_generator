# Critical Rules

## NEVER delete user data without explicit consent
- **Do NOT** call `cleanup_old()`, `delete_task()`, or any DELETE/DROP/TRUNCATE operation on the server database unless the user explicitly asks for it.
- **Do NOT** run `max_age=0` or any cleanup API call during testing — even on test data.
- If you need to clean up test data, ask the user first.
- The cleanup endpoint has a 5-minute minimum age floor, but do not rely on it — just don't call it.

## Always ask before destructive actions
Before any operation that could modify or remove data (cleanup, delete, schema changes, etc.), ask the user for approval.
