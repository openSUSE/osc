Feature: `osc develproject` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc develproject`
    When I execute osc with args "develproject"
    Then stdout is
        """
        test:devel/test-pkgA
        """
