Feature: Mission Control Stop — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to stop a mission
  that does not exist so callers can distinguish missing missions from
  state errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S48 Stop non-existent mission returns 404
    When I stop mission id 999999
    Then the mission control stop response status is 404
      And the mission control stop response detail mentions "Mission not found"