Feature: Scan Failure Handling (S06)
  As a system operator I want scan failures to be handled gracefully so that
  the mission continues through remaining locations.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI

  Scenario: S06 - Mission continues with SKIPPED location after scan failure
    Given CLI fault injection is enabled
      And a mission "s06-mission" with radius 20000 meters
      And three locations (T1, T2, T3) uploaded via CSV
      And the mission has been planned
    When I start the mission
    Then the mission reaches COMPLETED state
      And exactly 2 scan sessions are linked to the mission's locations
      And one location has status SKIPPED with reason SCAN_ERROR
    When I fetch mission scans for the current mission
      Then the response contains 2 items
