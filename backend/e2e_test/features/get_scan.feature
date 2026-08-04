Feature: Scan History — GET Scan Result (P1)
  As the system I must return 404 when a caller asks for a scan
  result that does not exist so callers can distinguish missing
  resources from server errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S23 GET scan result with non-existent ID returns 404
    When I get scan result with id 999999
    Then the scan get request returns status 404
      And the scan get detail mentions "Scan result not found"

  Scenario: S23b GET scan result with valid ID returns 200
    When I list scans with page 1 and page_size 1
      And I save the first scan result id as context.scan_get_id
    When I get scan result with id from context.scan_get_id
    Then the scan get request returns status 200
      And the scan get body has fields id, scan_session_id, rat, operator_name