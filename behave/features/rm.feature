Feature: `osc rm` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc rm` on multiple files
    When I execute osc with args "rm test-pkgA.spec test-pkgA.changes"
    Then the exit code is 0
     And I execute osc with args "status"
     And stdout is
        """
        D    test-pkgA.changes
        D    test-pkgA.spec
        """
