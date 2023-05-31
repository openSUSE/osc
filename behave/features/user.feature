Feature: Manage user accounts


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "api -X POST '/person?cmd=register' --file '{context.fixtures}/user/unicode.xml'"


@destructive
Scenario: Run `osc ls` under the newly created user that has a password with unicode characters
   Given I configure osc user "unicode" with password "Password with unicode characters 🚀🚀🚀"
    When I execute osc with args "ls test:factory"
    Then the exit code is 0
