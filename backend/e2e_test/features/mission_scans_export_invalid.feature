Feature: Mission Scans Export — Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests a scan export
  for a mission that does not exist so callers can distinguish missing
  missions from empty exports.

  Background:
    Given the backend is running on port 8001

  Scenario: S41 Export scans for non-existent mission returns 404
    When I export scans for mission id 999999
    Then the mission scans export response status is 404
      And the mission scans export response detail mentions "Mission not found"