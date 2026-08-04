Feature: Mission Lifecycle — List with Pagination & Status Filter (P1)
  As the system I must support paginated mission listing with optional
  status filtering so clients can efficiently browse large mission sets.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S20 List missions with status filter returns correct page
    Given a mission "s20-idle" with radius 10000 meters
      And three locations (M1, M2, M3) uploaded via CSV
      And the mission has been planned
    When I get all missions with status "IDLE"
    Then the list request returns status 200
      And the list total is greater than 0
      And the list items count is within page size
    When I get all missions with status "RUNNING"
    Then the list request returns status 200
      And the list total is 0
    When I get all missions with page 1 and page size 2
    Then the list items count is less than or equal to 2