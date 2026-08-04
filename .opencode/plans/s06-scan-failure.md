# Plan: S06 - Scan Failure Mid-Run (Mission Continues)

## Background

**S06** from `ADDITIONAL_E2E_PLAN.md`:
> Configure mock scanner to fail on the 2nd tower.
> Run mission → expect COMPLETED with `visited_locations = N-1` and one location marked `SKIPPED` with reason `SCAN_ERROR`.

**Problem observed:** The initial test enabled a global `MOCK_CLI_FAIL=1` fault injection via `PUT /test/cli/mock/fail`. This caused **ALL 3 scans** to fail (every tower skipped), not just one.

**Root cause:** `CLIAdapter.execute()` checked `os.environ.get("MOCK_CLI_FAIL")` as a global flag. The executor's exception handler correctly catches CLIError and marks a location SKIPPED, but the test injected fail for every scan call.

## Proposed Fix

### 1. Replace global fault injection with per-call counter

**File:** `backend/app/cli/adapter.py`
- Change the check from `os.environ.get("MOCK_CLI_FAIL")` to a decrementing counter:
  ```python
  # Test-only: MOCK_CLI_FAIL_OCCURRENCES=N raises for next N calls, then self-disables
  remaining = os.environ.get("MOCK_CLI_FAIL_OCCURRENCES")
  if remaining is not None:
      n = int(remaining)
      if n > 0:
          os.environ["MOCK_CLI_FAIL_OCCURRENCES"] = str(n - 1)
          raise CLIError(f"Simulated CLI failure (remaining={n-1})")
  ```
- This means "fail the next N CLI calls" instead of "fail forever".

### 2. Update test endpoint

**File:** `backend/app/gps/test_management.py`
- Change `PUT /test/cli/mock/fail` payload from `{"fail": true}` to `{"occurrences": 1}`.
- Set `MOCK_CLI_FAIL_OCCURRENCES=1` on enable, clear on disable.
- Add `GET /test/cli/mock/fail` that returns `{"occurrences": N}`.

### 3. Update feature file

**File:** `backend/e2e_test/features/scan_failure.feature`
- Keep scenario as-is (3 locations, enable CLI fault injection, expect COMPLETED with 2 sessions and 1 SKIPPED).

### 4. Update step definitions

**File:** `backend/e2e_test/features/steps/mission_steps.py`
- Change `CLI fault injection is enabled` step to use `{"occurrences": 1}`.
- Add a step `Given CLI fault injection for exactly {n} scan(s)` for flexibility.
- Verify in `then` that `visited_locations == 2` and exactly 1 location is SKIPPED with reason `SCAN_ERROR`.

### 5. Update environment.py cleanup
- `after_scenario` already resets `/test/cli/mock/fail` to `{"fail": false}`.
- Change to `{"occurrences": 0}` to clear the counter.

## Why This Works

The mission executor calls `CLIAdapter.execute()` once per tower. With `occurrences=1`, the **first** call raises `CLIError`, executor catches it, marks that location `SKIPPED`, emits `mission_skipped` event, and continues to the next tower. The next two towers succeed normally.

## Implementation Steps

1. **Modify `backend/app/cli/adapter.py`** — replace global check with decrementing counter.
2. **Modify `backend/app/gps/test_management.py`** — update CLI fail endpoint to use `occurrences`.
3. **Update `backend/e2e_test/features/steps/mission_steps.py`** — fix step definition for CLI fault injection.
4. **Update `backend/e2e_test/features/environment.py`** — reset occurrences to 0 in `after_scenario`.
5. **Run S06 test** — verify: COMPLETED, 2 scan sessions, 1 SKIPPED with SCAN_ERROR.
6. **Run all e2e tests** — confirm no regression.

## Files to Edit
- `backend/app/cli/adapter.py`
- `backend/app/gps/test_management.py`
- `backend/e2e_test/features/steps/mission_steps.py`
- `backend/e2e_test/features/environment.py`

## Expected Result
- Scenario passes: Mission completes with 2/3 towers visited, 1 skipped due to SCAN_ERROR.
