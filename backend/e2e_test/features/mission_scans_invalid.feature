Feature: Mission Scans — List by Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests scans
  for a mission that does not exist so callers can distinguish
  missing missions from empty results.

  Background:
    Given the backend is running on port 8001

  Scenario: S28 List scans for non-existent mission returns 404
    When I get mission scans with mission id 999999
    Then the mission scan list status is 404
      And the mission scan list detail mentions "Mission not found"