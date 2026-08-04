Feature: Mission Route Skip — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to skip a location
  on a mission that does not exist so callers can distinguish missing
  missions from validation errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S45 Skip route location for non-existent mission returns 404
    When I skip route location 1 for mission id 999999
    Then the mission route skip response status is 404
      And the mission route skip response detail mentions "Mission not found"