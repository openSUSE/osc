Feature: `osc linkpac` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Run `osc linkpac`
    When I execute osc with args "linkpac test:factory/test-pkgA home:Admin"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin/test-pkgA/_link"
     And stdout contains "<link project=\"test:factory\" package=\"test-pkgA\">"


@destructive
Scenario: Run `osc linkpac --disable-build`
    When I execute osc with args "linkpac test:factory/test-pkgA home:Admin --disable-build"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin/test-pkgA/_link"
     And stdout contains "<link project=\"test:factory\" package=\"test-pkgA\">"
     And I execute osc with args "api /source/home:Admin/test-pkgA/_meta"
     And stdout contains "<build>\s*<disable/>\s*</build>"


@destructive
Scenario: Run `osc linkpac --disable-publish`
    When I execute osc with args "linkpac test:factory/test-pkgA home:Admin --disable-publish"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin/test-pkgA/_link"
     And stdout contains "<link project=\"test:factory\" package=\"test-pkgA\">"
     And I execute osc with args "api /source/home:Admin/test-pkgA/_meta"
     And stdout contains "<publish>\s*<disable/>\s*</publish>"


@destructive
Scenario: Run `osc linkpac on a locked package`
   Given I execute osc with args "lock test:factory/test-pkgA"
    When I execute osc with args "linkpac test:factory/test-pkgA home:Admin/test-pkgA"
    Then the exit code is 0
