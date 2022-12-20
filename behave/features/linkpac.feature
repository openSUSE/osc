Feature: `osc linkpac` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Run `osc linkpac on a locked package`
   Given I execute osc with args "lock test:factory/test-pkgA"
    When I execute osc with args "linkpac test:factory/test-pkgA home:Admin/test-pkgA"
    Then the exit code is 0
