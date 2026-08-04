Feature: Mission Locations — Bulk Delete by Upload Batch (P1)
  As the system I must allow operators to bulk-delete the locations of a previous upload batch
  so that an entire upload can be reverted with a single call, without touching locations from
  newer batches.

  Background:
    Given the backend is running on port 8001
    And the lte-scanner service is active with mock GPS and CLI
    And GPS fault injection is disabled

  Scenario: S10 Bulk delete by upload_batch removes only that batch's locations
    Given a mission "bulk-a" with radius 20000 meters
      And three locations (B1, B2, B3) uploaded via CSV for batch "first"
      And two locations (B4, B5) uploaded via CSV for batch "second"
    When I bulk-delete by the "first" upload batch id for mission "bulk-a"
    Then the bulk-delete request returns status 200
      And the bulk-delete response reports 3 locations deleted
      And only "B4" and "B5" remain in mission "bulk-a" location list
      And the mission "bulk-a" has 2 locations
      And I delete the mission "bulk-a"