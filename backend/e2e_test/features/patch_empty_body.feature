Feature: Mission Lifecycle — PATCH Empty Body Validation (P1)
  As the system I must reject empty PATCH bodies so clients are guided
  to provide at least one valid update field.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S17 PATCH mission with empty body returns 422
    Given a mission "patch-empty" with radius 10000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I send an empty PATCH to mission "patch-empty"
    Then the patch request returns status 422
      And the mission name is still "patch-empty"