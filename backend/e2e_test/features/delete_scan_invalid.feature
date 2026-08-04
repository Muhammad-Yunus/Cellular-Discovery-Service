Feature: Scan History — DELETE by Non-Existent ID (P1)
  As the system I must return 404 when a caller attempts to
  delete a scan result that does not exist so callers can
  distinguish missing records from server errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S33 DELETE scan by non-existent id returns 404
    When I delete scan with id 999999
    Then the scan delete status is 404
      And the scan delete detail mentions "Scan result not found"