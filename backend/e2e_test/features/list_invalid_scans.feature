Feature: Scan History — List with Invalid Filters (P1)
  As the system I must reject invalid filter parameters for the scan
  history endpoint so callers receive a clear 422 instead of silently
  returning all results.

  Background:
    Given the backend is running on port 8001

  Scenario: S22 List scans with invalid rat filter returns 422
    When I get scans with rat "BOGUS"
    Then the scan list status is 422
      And the scan list detail mentions "Only GSM, LTE, UMTS, or ALL"

  Scenario: S22b List scans with inverted time range returns 422
    When I get scans with start_time "2026-08-04T00:00:00" and end_time "2026-08-03T00:00:00"
    Then the scan list status is 422
      And the scan list detail mentions "start_time cannot be greater than end_time"