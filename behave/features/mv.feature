Feature: `osc mv` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc mv <file> <new-name>` in a package checkout
    When I execute osc with args "mv test-pkgA.changes new-name.changes"
    Then the exit code is 0
     And I execute osc with args "status"
     And stdout is
     """
     A    new-name.changes
     D    test-pkgA.changes
     """
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes" does not exist
     And file "{context.osc.temp}/test:factory/test-pkgA/new-name.changes" exists
