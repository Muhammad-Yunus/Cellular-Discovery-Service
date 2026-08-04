Feature: Mission Lifecycle — Patch IDLE Mission with Invalid Data (P1)
  As the system I must reject malformed PATCH payloads so that corrupted
  mission data is never written to the database.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S15 Patch IDLE mission with invalid name returns 422
    Given a mission "patch-bad" with radius 15000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I patch the mission "patch-bad" with name "   "
    Then the patch request returns status 422
      And the mission name is still "patch-bad"
    When I patch the mission "patch-bad" with radius -500 meters
    Then the patch request returns status 422
      And the mission radius is still 15000 meters