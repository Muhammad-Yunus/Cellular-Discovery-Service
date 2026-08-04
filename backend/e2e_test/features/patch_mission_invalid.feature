Feature: Mission — PATCH with Invalid Radius (P1)
  As the system I must reject PATCH requests that set a negative
  or zero radius so that callers cannot corrupt a mission's
  geometry with an invalid value.

  Background:
    Given the backend is running on port 8001

  Scenario: S29 PATCH mission with zero radius returns 422
    When I patch mission with id 881 and radius 0 meters
    Then the mission patch status is 422
      And the mission patch detail mentions "greater than 0"