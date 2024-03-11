Feature: `osc build` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "co test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc build --just-print-buildroot`
    When I execute osc with args "build --just-print-buildroot"
    Then the exit code is 0
