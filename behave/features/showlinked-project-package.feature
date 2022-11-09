Feature: `osc showlinked` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin --force"


Scenario: Run `osc showlinked <project> <package>`
    When I execute osc with args "showlinked test:factory test-pkgA"
    Then stdout is
        """
        home:Admin/test-pkgA
        """


Scenario: Run `osc showlinked <project>/<package>`
    When I execute osc with args "showlinked test:factory/test-pkgA"
    Then stdout is
        """
        home:Admin/test-pkgA
        """
