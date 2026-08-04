Feature: Mission Location Bulk-Delete — Non-Existent Mission (P1)
  As the system I must return 404 when a caller requests a bulk-delete
  for a mission that does not exist so callers can distinguish missing
  missions from empty delete results.

  Background:
    Given the backend is running on port 8001

  Scenario: S43 Bulk-delete locations for non-existent mission returns 404
    When I bulk-delete locations for mission id 999999 with batch "test-batch"
    Then the mission locations bulk-delete response status is 404
      And the mission locations bulk-delete response detail mentions "Mission not found"