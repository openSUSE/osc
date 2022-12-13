Feature: `osc setlinkrev` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin --force"


Scenario: Run `osc setlinkrev <project>`
    When I execute osc with args "setlinkrev home:Admin"
    Then stdout is
        """
        Set link revision of package home:Admin/test-pkgA to 3
        """


Scenario: Run `osc setlinkrev <project> --revision`
    When I execute osc with args "setlinkrev home:Admin --revision=2"
    Then the exit code is 2


Scenario: Run `osc setlinkrev <project> --unset`
   Given I execute osc with args "setlinkrev home:Admin test-pkgA --revision=2"
     And stdout is
        """
        Set link revision of package home:Admin/test-pkgA to 2
        """
    When I execute osc with args "setlinkrev home:Admin --unset"
    Then stdout is
        """
        Removed link revision from package home:Admin/test-pkgA
        """
