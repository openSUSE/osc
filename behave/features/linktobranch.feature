Feature: `osc linktobranch` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin"


@destructive
Scenario: Run `osc linktobranch <project> <package>`
    When I execute osc with args "linktobranch home:Admin test-pkgA"
    Then the exit code is 0


@destructive
Scenario: Run `osc linktobranch <project>`
    When I execute osc with args "linktobranch home:Admin"
    Then the exit code is 1


@destructive
Scenario: Run `osc linktobranch` from a package working copy
   Given I execute osc with args "co home:Admin/test-pkgA"
     And I set working directory to "{context.osc.temp}/home:Admin/test-pkgA"
    When I execute osc with args "linktobranch"
    Then the exit code is 0
