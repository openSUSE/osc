Feature: `osc setlinkrev` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin --force"


Scenario: Run `osc setlinkrev <project> <package>`
    When I execute osc with args "setlinkrev home:Admin test-pkgA"
    Then stdout is
        """
        Set link revision of package home:Admin/test-pkgA to 3
        """


Scenario: Run `osc setlinkrev <project>/<package>`
    When I execute osc with args "setlinkrev home:Admin/test-pkgA"
    Then stdout is
        """
        Set link revision of package home:Admin/test-pkgA to 3
        """


Scenario: Run `osc setlinkrev <project> <package> --revision`
    When I execute osc with args "setlinkrev home:Admin test-pkgA --revision=2"
    Then stdout is
        """
        Set link revision of package home:Admin/test-pkgA to 2
        """


Scenario: Run `osc setlinkrev <project> <package> --unset`
    When I execute osc with args "setlinkrev home:Admin test-pkgA --unset"
    Then stdout is
        """
        Removed link revision from package home:Admin/test-pkgA
        """
