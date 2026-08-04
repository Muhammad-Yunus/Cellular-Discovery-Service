Feature: Mission Lifecycle — Delete IDLE Mission (P1)
  As the system I must allow operators to delete a mission that is in IDLE/READY state
  so that completed or abandoned test missions can be fully cleaned up.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S11 Delete a mission in IDLE status returns 200 and mission is gone
    Given a mission "delete-idle" with radius 20000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I delete the mission "delete-idle" via the API
    Then the mission delete request returns status 200
      And the response message is "Mission deleted successfully"
      And getting the mission "delete-idle" returns status 404