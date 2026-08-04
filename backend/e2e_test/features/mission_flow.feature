Feature: Mission Planner End-to-End Flow
  As a field operator I want to plan, start and complete a mission so that network scans are recorded at each tower.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI

  Scenario: Full mission workflow with scan collection
    Given a mission "field-mission" with radius 20000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I start the mission
    Then the mission reaches COMPLETED state
      And exactly 3 scan sessions are linked to the mission's locations
    When I fetch mission scans for the current mission
      Then the response contains 3 items with non-null mission_location_id
    When I export mission scans as CSV
      Then the download includes columns: cellular_tower_id, cellular_tower_name, mission_location_id
