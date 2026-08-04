Feature: Mission Control Pause — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to pause a mission
  that does not exist so callers can distinguish missing missions from
  state errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S47 Pause non-existent mission returns 404
    When I pause mission id 999999
    Then the mission control pause response status is 404
      And the mission control pause response detail mentions "Mission not found"