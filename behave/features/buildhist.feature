Feature: `osc buildhist` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc buildist <project>/<package> <repository>/<arch>`
    When I execute osc with args "buildhist test:factory/test-pkgA standard/x86_64"
    Then the exit code is 0


Scenario: Run `osc buildist <project>/<package> <repository>/<arch> --limit`
    When I execute osc with args "buildhist test:factory/test-pkgA standard/x86_64 --limit=1"
    Then the exit code is 0


Scenario: Run `osc buildist <repository>/<arch>` from a package checkout
   Given I execute osc with args "co test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
    When I execute osc with args "buildhist standard/x86_64"
    Then the exit code is 0


Scenario: Run `osc buildist <repository>/<arch>` from outside a package checkout
    When I execute osc with args "buildhist standard/x86_64"
    Then the exit code is 1


Scenario: Run `osc buildist <repository>/<arch>` from a project checkout
   Given I execute osc with args "co test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"
    When I execute osc with args "buildhist standard/x86_64"
    Then the exit code is 1
