Feature: `osc develproject` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc develproject`
    When I execute osc with args "develproject test:factory"
    Then the exit code is 1
     And stderr is
        """
        *** Error: Please specify a package
        """
