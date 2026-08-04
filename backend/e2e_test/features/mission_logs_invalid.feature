Feature: Mission Logs — Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests logs for a mission
  that does not exist so callers can distinguish missing missions from
  empty log lists.

  Background:
    Given the backend is running on port 8001

  Scenario: S49 Get logs for non-existent mission returns 404
    When I get logs for mission id 999999
    Then the mission logs response status is 404
      And the mission logs response detail mentions "Mission not found"