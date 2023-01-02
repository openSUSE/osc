Feature: `osc copypac` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Run `osc copypac <project>/<package> <target-project>`
    When I execute osc with args "copypac test:factory/test-pkgA home:Admin"
    Then the exit code is 0


@destructive
Scenario: Run `osc copypac <project>/<package> <target-project>/<target-package>`
    When I execute osc with args "copypac test:factory/test-pkgA home:Admin/test-pkgAA"
    Then the exit code is 0


Scenario: Run `osc copypac` where the source and target are the same
    When I execute osc with args "copypac test:factory/test-pkgA test:factory"
    Then the exit code is 1
