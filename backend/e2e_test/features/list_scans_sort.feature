Feature: Scan History — List with Sort Parameter (P1)
  As the system I must support a `sort` query parameter on the scan
  history endpoint so that callers can order results by any of the
  supported columns (`scan_time`, `operator_name`, `mcc`, `mnc`, `rat`)
  in either ascending or descending direction.

  Background:
    Given the backend is running on port 8001

  # ----------------------------------------------------------------
  # ASC sort
  # ----------------------------------------------------------------

  Scenario: S30 List scans sorted by operator_name ascending
    When I list scans with sort "operator_name" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by operator_name ascending

  Scenario: S31 List scans sorted by mcc ascending
    When I list scans with sort "mcc" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by mcc ascending

  Scenario: S32 List scans sorted by mnc ascending
    When I list scans with sort "mnc" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by mnc ascending

  Scenario: S33 List scans sorted by rat ascending
    When I list scans with sort "rat" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by rat ascending

  Scenario: S34 List scans sorted by scan_time ascending
    When I list scans with sort "scan_time" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by scan_time ascending

  # ----------------------------------------------------------------
  # DESC sort
  # ----------------------------------------------------------------

  Scenario: S35 List scans sorted by -operator_name descending
    When I list scans with sort "-operator_name" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by operator_name descending

  Scenario: S36 List scans sorted by -mcc descending
    When I list scans with sort "-mcc" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by mcc descending

  Scenario: S37 List scans sorted by -mnc descending
    When I list scans with sort "-mnc" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by mnc descending

  Scenario: S38 List scans sorted by -rat descending
    When I list scans with sort "-rat" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by rat descending

  Scenario: S39 List scans sorted by -scan_time descending
    When I list scans with sort "-scan_time" and page_size 10
    Then the scan list status is 200
      And the scan list body has total greater than 0
      And the scan list items are sorted by scan_time descending

  # ----------------------------------------------------------------
  # Edge case: unknown sort key falls back to scan_time DESC
  # ----------------------------------------------------------------

  Scenario: S40 List scans with unknown sort key falls back to scan_time desc
    When I list scans with sort "bogus_field" and page_size 10
    Then the scan list status is 200
      And the scan list items are sorted by scan_time descending
