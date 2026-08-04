Feature: Scan History — GET by Non-Existent ID (P1)
  As the system I must return 404 when a caller requests a scan
  result that does not exist so callers can distinguish missing
  records from server errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S32 GET scan by non-existent id returns 404
    When I get scan with id 999999
    Then the scan get status is 404
      And the scan get detail mentions "Scan result not found"