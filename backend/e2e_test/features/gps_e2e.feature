Feature: GPS Provider E2E — Provider Switching, WebSocket, Fault Tolerance

  As a system operator I want GPS provider switching and fault tolerance to be validated
  end-to-end so that the operator dashboard, mission execution, and location services
  work correctly across all GPS provider types.

  Background:
    Given the backend is running on port 8001
    And GPS fault injection is disabled
    And the lte-scanner service is active with mock GPS and CLI

  Scenario: GPS-WS-01 Switch GPS provider between mock and cli via settings
    When I set GPS provider to "mock"
    When I retrieve the current GPS provider setting
    Then the GPS provider setting should be "mock"
    When I update the GPS provider setting to "cli"
    Then the GPS provider setting should be "cli"

  Scenario: GPS-WS-02 WebSocket /ws/gps broadcasts valid location updates
    When I set GPS provider to "mock"
    Given a mission "gps-ws-mission" with radius 20000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I connect to the GPS WebSocket endpoint
      And I wait for 3 location updates
    Then the WebSocket should receive 3 frames
      And each frame should contain a valid latitude and longitude
      And the latitude should be a finite number
      And the longitude should be a finite number
    When I disconnect from the GPS WebSocket
    Then I delete the mission "gps-ws-mission"

  Scenario: GPS-WS-03 Transient GPS fault during mission recovers automatically
    When I set GPS provider to "mock"
    Given a mission "gps-recovery-mission" with radius 20000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I start the mission "gps-recovery-mission" (fire-and-forget)
      And I wait for it to enter RUNNING state
    Then the mission "gps-recovery-mission" status is RUNNING
    When I simulate a GPS failure via test management
    Then the mission "gps-recovery-mission" status remains RUNNING or transitions to PAUSED
    When I restore normal GPS operation via test management
    Then the mission "gps-recovery-mission" status is RUNNING or COMPLETED or STOPPED

  Scenario: GPS-WS-04 Invalid provider type is rejected at settings update
    When I attempt to set GPS provider to "invalid-provider"
    Then the settings update returns status 422

  Scenario: GPS-WS-05 Concurrent GPS reads under load return valid locations
    When I set GPS provider to "mock"
    Given a mission "gps-concurrent-mission" with radius 20000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I connect to the GPS WebSocket and capture 5 updates
      And I connect a second WebSocket and capture 5 updates
    Then both WebSockets should receive 5 frames each
      And all frames should contain valid coordinates
    When I disconnect both WebSockets
    Then I delete the mission "gps-concurrent-mission"
