Feature: `osc rdiff` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc rdiff <project>/<package> <target-project>/<target-package>`
    When I execute osc with args "rdiff test:factory/test-pkgA test:factory/test-pkgA"
    Then the exit code is 0


Scenario: Run `osc rdiff <project>/<package> <target-project>`
    When I execute osc with args "rdiff test:factory/test-pkgA test:factory"
    Then the exit code is 0


Scenario: Run `osc rdiff <project>/<package>`
    When I execute osc with args "rdiff test:factory/test-pkgA"
    Then the exit code is 0


Scenario: Run `osc rdiff <project>/<package> --change`
    When I execute osc with args "rdiff test:factory/test-pkgA --change=1"
    Then the exit code is 0
