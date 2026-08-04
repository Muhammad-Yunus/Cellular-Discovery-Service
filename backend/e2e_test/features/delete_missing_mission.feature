Feature: Mission Lifecycle — DELETE Non-Existent Mission (P1)
  As the system I must clearly signal when DELETE targets a mission that
  does not exist so callers don't silently fail.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S18 DELETE a non-existent mission ID returns 404
    When I delete mission id 999999 via the API
    Then the mission delete request returns status 404
      And the delete detail mentions "not found"
    When I get mission id 999999
    Then the mission get request returns status 404
      And the delete detail mentions "not found"