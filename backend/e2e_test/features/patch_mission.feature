Feature: Mission Lifecycle — Patch IDLE Mission (P1)
  As an operator I must be able to update an IDLE mission's editable fields
  (name, radius, tty port, start location) so that pre-run configuration
  mistakes can be fixed before the mission is started.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S13 Patch mission in IDLE/READY state updates fields and clears sequence on structural change
    Given a mission "patch-mission" with radius 10000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I patch the mission "patch-mission" with name "patch-mission-renamed"
    Then the patch request returns status 200
      And the mission name is "patch-mission-renamed"
      And the mission radius is 10000 meters
      And the planned route has 3 locations in sequence
    When I patch the mission "patch-mission" with radius 25000 meters
    Then the patch request returns status 200
      And the mission name is "patch-mission-renamed"
      And the mission radius is 25000 meters
      And the planned route has no sequence order
    When I replan the mission "patch-mission"
    Then the replan request returns status 200
      And the planned route has 3 locations in sequence