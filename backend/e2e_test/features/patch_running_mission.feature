Feature: Mission Lifecycle — Patch RUNNING Mission Guard (P1)
  As the system I must refuse to update a mission that is currently active
  so that in-progress configuration cannot be corrupted mid-flight.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S14 Patch a RUNNING mission returns 409 Conflict
    Given a mission "patch-run" with radius 20000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I start the mission "patch-run" (fire-and-forget)
    Then the mission "patch-run" reached RUNNING state
    When I patch the mission "patch-run" with name "patch-run-renamed"
    Then the patch request returns status 409
      And the patch detail mentions "Cannot update mission while it is RUNNING"
      And getting the mission "patch-run" returns status 200
    When I stop the mission "patch-run"
    Then the mission "patch-run" reaches STOPPED state
    When I delete the mission "patch-run" via the API
    Then the mission delete request returns status 200