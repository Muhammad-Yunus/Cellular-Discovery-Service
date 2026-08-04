Feature: Scan History — List with Search Filter (P1)
  As the system I must support an operator-search filter on the scan
  history endpoint so that callers can narrow down results by
  operator name.

  Background:
    Given the backend is running on port 8001

  Scenario: S27 List scans with matching operator returns at least 1 item
    When I list scans with search "Telkomsel" and page_size 5
    Then the scan list status is 200
      And the scan list items count is at least 1
      And all scan list items have operator_name matching "Telkomsel"

  Scenario: S27b List scans with non-matching search returns empty items
    When I list scans with search "nonexistent_operator_xyz" and page_size 5
    Then the scan list status is 200
      And the scan list body has total 0