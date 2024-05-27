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


Scenario: Run `osc mv <file> <new-name>` several times
    When I execute osc with args "mv test-pkgA.changes test-pkgA.changes-1"
    Then the exit code is 0
     And I execute osc with args "status"
     And stdout is
     """
     D    test-pkgA.changes
     A    test-pkgA.changes-1
     """
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes" does not exist
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes-1" exists
    When I execute osc with args "mv test-pkgA.changes-1 test-pkgA.changes-2"
    Then the exit code is 0
     And I execute osc with args "status"
     And stdout is
     """
     D    test-pkgA.changes
     A    test-pkgA.changes-2
     """
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes" does not exist
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes-2" exists
    When I execute osc with args "mv test-pkgA.changes-2 test-pkgA.changes-3"
    Then the exit code is 0
     And I execute osc with args "status"
     And stdout is
     """
     D    test-pkgA.changes
     A    test-pkgA.changes-3
     """
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes" does not exist
     And file "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.changes-3" exists
