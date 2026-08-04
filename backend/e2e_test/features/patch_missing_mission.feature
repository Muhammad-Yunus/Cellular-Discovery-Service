Feature: Mission Lifecycle — Patch Non-Existent Mission (P1)
  As the system I must clearly signal when a PATCH targets a mission that
  does not exist so callers don't silently corrupt state.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S16 Patch a non-existent mission ID returns 404
    When I patch mission id 999999 with name "patch-404-renamed"
    Then the patch request returns status 404
      And the patch detail mentions "not found"
    When I patch mission id 999999 with radius 15000 meters
    Then the patch request returns status 404
      And the patch detail mentions "not found"