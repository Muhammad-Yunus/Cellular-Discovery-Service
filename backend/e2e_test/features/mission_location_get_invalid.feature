Feature: Mission Locations — GET Location for Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests a location
  that belongs to a mission which does not exist so callers can
  distinguish missing missions from missing locations.

  Background:
    Given the backend is running on port 8001

  Scenario: S36 GET location for non-existent mission returns 404
    When I get mission location 999999 for mission id 999999
    Then the mission location get status is 404
      And the mission location get detail mentions "Mission not found"