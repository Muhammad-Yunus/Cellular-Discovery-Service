Feature: Mission — Create with Invalid Radius (P1)
  As the system I must reject mission creation requests with a
  radius less than or equal to zero so that invalid missions are
  never created.

  Background:
    Given the backend is running on port 8001

  Scenario: S26 Create mission with zero radius returns 422
    When I create mission with name "s26-zero" and radius 0 meters
    Then the mission create status is 422
      And the mission create detail mentions "greater than 0"

  Scenario: S26b Create mission with negative radius returns 422
    When I create mission with name "s26-neg" and radius -100 meters
    Then the mission create status is 422
      And the mission create detail mentions "greater than 0"