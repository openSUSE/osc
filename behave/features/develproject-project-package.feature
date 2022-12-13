Feature: `osc develproject` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc develproject`
    When I execute osc with args "develproject test:factory test-pkgA"
    Then stdout is
        """
        test:devel/test-pkgA
        """


Scenario: Run `osc develproject`
    When I execute osc with args "develproject test:factory test-pkgB"
    Then the exit code is 1
     And stderr is
        """
        Package test:factory/test-pkgB has no devel project
        """


Scenario: Run `osc develproject`
    When I execute osc with args "develproject test:factory/test-pkgB"
    Then the exit code is 1
     And stderr is
        """
        Package test:factory/test-pkgB has no devel project
        """
