Feature: Scan History — List with Invalid RAT (P1)
  As the system I must reject scan list requests with an unsupported
  RAT filter so callers receive a clear validation error instead
  of silently ignoring the parameter.

  Background:
    Given the backend is running on port 8001

  Scenario: S31 List scans with invalid RAT returns 422
    When I list scans with rat "INVALID"
    Then the scan list status is 422
      And the scan list detail mentions "Only GSM, LTE, UMTS, or ALL is allowed"