Feature: Settings — PUT Invalid Body (P1)
  As the system I must reject non-list payloads for the bulk
  settings update endpoint so callers cannot accidentally overwrite
  a single setting with a malformed object.

  Background:
    Given the backend is running on port 8001

  Scenario: S25 PUT settings with object body returns 422
    When I put settings with object body {"key": "TEST_BAD", "value": "x"}
    Then the settings put status is 422
      And the settings put detail mentions "Input should be a valid list"