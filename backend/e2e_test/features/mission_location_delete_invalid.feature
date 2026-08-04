Feature: Mission Locations — DELETE Location for Non-Existent Mission (P1)
  As the system I must return 404 when a caller attempts to delete
  a location belonging to a mission that does not exist so callers
  can distinguish missing missions from missing locations.

  Background:
    Given the backend is running on port 8001

  Scenario: S35 DELETE location for non-existent mission returns 404
    When I delete mission location 1 for mission id 999999
    Then the mission location delete status is 404
      And the mission location delete detail mentions "Mission not found"