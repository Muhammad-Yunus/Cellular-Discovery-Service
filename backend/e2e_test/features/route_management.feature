Feature: Route Management (P1)
  As the system I must allow operators to manually reorder and manage the planned route sequence so that field agents can visit towers in any desired order.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S07 Reorder route manually changes the planned sequence and distances
    Given a mission "route-a" with radius 20000 meters
      And five locations (R1-R5) uploaded via CSV
      And the mission has been planned
      And I capture the original route sequence
    When I reorder the route to ["R3", "R1", "R4", "R2", "R5"]
      And I fetch the route for the current mission
    Then the route reflects the new sequence order
      And distances and bearings are recomputed
      And I delete the mission "route-a"
