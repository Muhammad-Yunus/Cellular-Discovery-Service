Feature: Route Management — Skip Mid-Planning (P1)
  As the system I must allow operators to skip a planned location mid-planning so that
  a tower that should not be visited is removed from the route sequence before the mission starts.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S08 Skip a location mid-planning changes status, clears sequence, and decrements total_locations
    Given a mission "skip-a" with radius 20000 meters
      And four locations (K1-K4) uploaded via CSV
      And the mission has been planned
      And the planned route has 4 locations in sequence
    When I skip the location "K2"
    Then the skip request returns status 200
      And the location "K2" has status SKIPPED
      And the location "K2" has no sequence order
      And the planned route has 3 locations in sequence
      And the location "K2" is not present in the route
      And I delete the mission "skip-a"
