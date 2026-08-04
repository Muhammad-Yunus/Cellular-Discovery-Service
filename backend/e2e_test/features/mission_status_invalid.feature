Feature: Mission Control — Status for Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests status
  of a mission that does not exist so callers can distinguish
  missing missions from other errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S38 Get status for non-existent mission returns 404
    When I get status for mission id 999999
    Then the mission status response status is 404
      And the mission status response detail mentions "Mission not found"