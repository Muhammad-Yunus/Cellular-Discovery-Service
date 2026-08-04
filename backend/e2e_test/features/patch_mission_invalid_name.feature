Feature: Mission — PATCH with Invalid Name (P1)
  As the system I must reject PATCH requests that set an empty
  or whitespace-only mission name so that mission identity is
  never lost.

  Background:
    Given the backend is running on port 8001

  Scenario: S30 PATCH mission with empty name returns 422
    When I patch mission with id 881 and name ""
    Then the mission patch status is 422
      And the mission patch detail mentions "Mission name is required"