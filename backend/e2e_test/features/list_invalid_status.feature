Feature: Mission Lifecycle — List with Invalid Status Filter (P1)
  As the system I must reject invalid status filters so callers receive
  a clear 422 instead of silently returning all missions.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S21 List missions with invalid status filter returns 422
    When I get all missions with status "BOGUS"
    Then the list request returns status 422
      And the list detail mentions "Invalid mission status"