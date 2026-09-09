# Autonomous Execution Rules for SchoolSM

## Auto-Execution and Approval Policy
1. **Direct Execution**:
   - Execute user requests immediately and autonomously.
   - Do NOT stop to ask for confirmation or manual approval for routine code changes, file edits, or terminal commands (e.g. running tests, checking status, database migrations).
   - Only ask for confirmation if an operation would permanently destroy critical uncommitted data.

2. **Skip Interactive Planning Approvals**:
   - For implementation plans, always proceed directly into execution without requiring the user to manually click "Proceed" or "Submit".
   - Set `RequestFeedback: false` on implementation plans so the UI does not block execution waiting for approval.

3. **Verify and Deliver**:
   - Proactively run verification (tests, linter, syntax checks) after making changes.
   - Present final completed results directly to the user in a concise, structured response.
