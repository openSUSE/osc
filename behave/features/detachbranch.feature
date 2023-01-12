Feature: `osc detachbranch` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin"


@destructive
Scenario: Run `osc detachbranch <project> <package>`
    When I execute osc with args "detachbranch home:Admin test-pkgA"
    Then the exit code is 0


@destructive
Scenario: Run `osc detachbranch <project>`
    When I execute osc with args "detachbranch home:Admin"
    Then the exit code is 1


@destructive
Scenario: Run `osc detachbranch` from a package working copy
   Given I execute osc with args "co home:Admin/test-pkgA"
     And I set working directory to "{context.osc.temp}/home:Admin/test-pkgA"
    When I execute osc with args "detachbranch"
    Then the exit code is 0
