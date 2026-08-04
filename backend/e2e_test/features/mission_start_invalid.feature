Feature: Mission Control Start — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to start a mission
  that does not exist so callers can distinguish missing missions from
  state errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S46 Start non-existent mission returns 404
    When I start mission id 999999
    Then the mission control start response status is 404
      And the mission control start response detail mentions "Mission not found"