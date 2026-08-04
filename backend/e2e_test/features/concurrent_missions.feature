Feature: Concurrent Mission Guards (P0)
  As the system I must reject attempts to start more than one mission at the same time so that field resources (GPS / scanner) are not double-booked.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S01 Second mission start is rejected while first is RUNNING
    Given a mission "concurrent-a" with radius 15000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
      And a second mission "concurrent-b" with radius 15000 meters
      And three locations (T1, T2, T3) uploaded via CSV for mission "concurrent-b"
      And the second mission has been planned
    When I start the mission "concurrent-a" (fire-and-forget)
    Then the mission "concurrent-a" reached RUNNING state
    When I attempt to start the mission "concurrent-b"
    Then the start request returns status 409
    And the response detail mentions another mission is already running
    And the mission "concurrent-b" status is not RUNNING
    When I stop the mission "concurrent-a"
    Then the mission "concurrent-a" reaches STOPPED state
    And I delete the mission "concurrent-a"
    And I delete the mission "concurrent-b"

  Scenario: S02 Pause and resume work mid-mission without losing progress
    Given a mission "concurrent-a" with radius 15000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I start the mission "concurrent-a" (fire-and-forget)
    Then the mission "concurrent-a" reached RUNNING state
    When I pause the mission "concurrent-a"
    Then the mission "concurrent-a" status is PAUSED
    And the start endpoint rejects a second start for "concurrent-a" with 409
    When I resume the mission "concurrent-a"
    Then the mission "concurrent-a" status is RUNNING within 3 seconds
    # Mission should complete (or keep running) — no crash from pause/resume transition
    When I stop the mission "concurrent-a"
    Then the mission "concurrent-a" reaches STOPPED state
    And I delete the mission "concurrent-a"

  Scenario: S03 Mission auto-completes when all planned locations are visited
    # Radius 20km ensures the mock GPS location (-6.150, 106.896) is within range of
    # the uploaded tower (-6.200, 106.800) so the executor will visit it and trigger
    # mission_completed automatically.
    Given a mission "concurrent-a" with radius 20000 meters
      And one location uploaded via CSV at the mock GPS coordinates
      And the mission has been planned
    When I start the mission "concurrent-a" (fire-and-forget)
    Then the mission "concurrent-a" reaches COMPLETED state within 60 seconds
    And the mission "concurrent-a" reports 1 of 1 locations visited
    And the mission logs include a "mission_completed" event
    And I delete the mission "concurrent-a"

  Scenario: S04 Stop during STARTING window does not orphan the mission in RUNNING
    # The mission spends ~5s in STARTING (waiting for GPS_ok) before RUNNING. A stop
    # issued during this window must either: (a) succeed and keep status=STOPPED, or
    # (b) succeed and the status remains STOPPED after _run spawns. It MUST NOT be
    # left in RUNNING with no active task (orphan).
    Given a mission "concurrent-a" with radius 15000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I start the mission "concurrent-a" and immediately stop it
    Then the mission "concurrent-a" reaches a terminal state within 10 seconds
    And the mission "concurrent-a" status is not RUNNING
    And I delete the mission "concurrent-a"

  Scenario: S05 Starting a mission with no locations is rejected with 422
    # If a mission is created but no locations are uploaded/plan()ed, the start
    # endpoint must reject the request with 422 (Unprocessable Entity). This prevents
    # wasted GPS/scanner resources and ensures the contract (plan first → start)
    # is enforced at the API level.
    Given a mission "concurrent-a" with radius 15000 meters
    When I attempt to start the mission "concurrent-a"
    Then the start request returns status 422
    And the response detail mentions "no planned locations" or "Run plan"
    And I delete the mission "concurrent-a"

  Scenario: S06 GPS failure during start causes mission to fail gracefully with 503
    # If the GPS provider raises GPSError during the STARTING phase, the executor
    # must transition the mission to FAILED status, set a clear reason, and the
    # HTTP response must be 503 (Service Unavailable) — not a raw 500. After the
    # error is handled, the GPS service must be restored so future missions work
    # normally.
    Given a mission "concurrent-a" with radius 15000 meters
    And three locations (T1, T2, T3) uploaded via CSV
    And the mission has been planned
    And I simulate a GPS failure via test management
    When I attempt to start the mission "concurrent-a" expecting a non-200 status
    Then the start request returns status 503
    And the response detail mentions "GPS" or "not available" or "read"
    And the mission "concurrent-a" reaches FAILED state within 15 seconds
    And I restore normal GPS operation via test management
    And I delete the mission "concurrent-a"
