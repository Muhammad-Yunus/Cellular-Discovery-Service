Feature: Mission Locations — List for Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests locations
  for a mission that does not exist so callers can distinguish
  missing missions from empty results.

  Background:
    Given the backend is running on port 8001

  Scenario: S34 List locations for non-existent mission returns 404
    When I list mission locations with mission id 999999
    Then the mission location list status is 404
      And the mission location list detail mentions "Mission not found"