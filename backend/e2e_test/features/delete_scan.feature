Feature: Scan History — DELETE Scan Result (P1)
  As the system I must return 404 when a caller tries to delete a
  scan result that does not exist so callers receive a clear error.

  Background:
    Given the backend is running on port 8001

  Scenario: S24 DELETE scan result with non-existent ID returns 404
    When I delete scan result with id 999999
    Then the scan delete request returns status 404
      And the scan delete detail mentions "Scan result not found"