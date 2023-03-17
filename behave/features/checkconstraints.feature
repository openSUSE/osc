Feature: `osc checkconstraints` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc checkconstraints <project>/<package> <repository>/<arch>`
    When I execute osc with args "checkconstraints test:factory/test-pkgA standard/x86_64"
    Then the exit code is 0


Scenario: Run `osc checkconstraints` from a package working copy
   Given I execute osc with args "co test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
    When I execute osc with args "checkconstraints"
    Then the exit code is 0
