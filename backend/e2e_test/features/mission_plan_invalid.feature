Feature: Mission Planning — Plan Route for Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests a route
  plan for a mission that does not exist so callers can distinguish
  missing missions from planning errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S39 Plan route for non-existent mission returns 404
    When I plan route for mission id 999999
    Then the mission plan response status is 404
      And the mission plan response detail mentions "Mission not found"