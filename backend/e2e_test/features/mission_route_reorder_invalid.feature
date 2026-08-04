Feature: Mission Route Reorder — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to reorder a route
  for a mission that does not exist so callers can distinguish missing
  missions from validation errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S44 Reorder route for non-existent mission returns 404
    When I reorder route for mission id 999999 with items "[1, 2]"
    Then the mission route reorder response status is 404
      And the mission route reorder response detail mentions "Mission not found"