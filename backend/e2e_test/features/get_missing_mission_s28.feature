Feature: Mission Lifecycle — GET Non-Existent Mission (P1)
  As the system I must clearly signal when a GET targets a mission that
  does not exist so clients receive a proper 404 instead of an empty list.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S28 Get a non-existent mission ID returns 404
    When I get mission id 999999
    Then the mission get request returns status 404
      And the get mission detail mentions "not found"