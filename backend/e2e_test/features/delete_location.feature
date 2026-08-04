Feature: Mission Locations — Delete Single (P1)
  As the system I must allow operators to delete a single mission location from an upload before
  running so that a mis-uploaded or no-longer-needed tower can be removed cleanly.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S09 Delete single mission location reduces the location list by one
    Given a mission "delete-one" with radius 20000 meters
      And five locations (D1-D5) uploaded via CSV
      And the mission has been planned
    When I delete the location "D3" for mission "delete-one"
    Then the delete request returns status 200
      And the location "D3" is not present in mission "delete-one" location list
      And the mission "delete-one" has 4 locations
      And I delete the mission "delete-one"