Feature: Mission Location Upload — Non-Existent Mission (P1)
  As the system I must return 404 when a caller tries to upload locations
  for a mission that does not exist so callers can distinguish missing
  missions from validation errors.

  Background:
    Given the backend is running on port 8001

  Scenario: S42 Upload locations for non-existent mission returns 404
    When I upload an empty file to mission id 999999 locations
    Then the mission locations upload response status is 404
      And the mission locations upload response detail mentions "Mission not found"