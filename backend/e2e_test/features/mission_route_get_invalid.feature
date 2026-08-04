Feature: Mission Planning — Get Route for Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests the route
  for a mission that does not exist so callers can distinguish
  missing missions from empty routes.

  Background:
    Given the backend is running on port 8001

  Scenario: S40 Get route for non-existent mission returns 404
    When I get route for mission id 999999
    Then the mission route response status is 404
      And the mission route response detail mentions "Mission not found"