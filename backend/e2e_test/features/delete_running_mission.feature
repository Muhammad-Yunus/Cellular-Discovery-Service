Feature: Mission Lifecycle — Delete RUNNING Mission Guard (P1)
  As the system I must refuse to delete a mission that is currently active
  so that an in-progress mission cannot be wiped out by an operator mistake.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S12 Delete a RUNNING mission returns 409 Conflict
    Given a mission "delete-run" with radius 20000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I start the mission "delete-run" (fire-and-forget)
    Then the mission "delete-run" reached RUNNING state
    When I delete the mission "delete-run" via the API
    Then the mission delete request returns status 409
      And the mission delete detail mentions "Cannot delete mission while it is RUNNING"
      And getting the mission "delete-run" returns status 200
    When I stop the mission "delete-run"
    Then the mission "delete-run" reaches STOPPED state
    When I delete the mission "delete-run" via the API
    Then the mission delete request returns status 200