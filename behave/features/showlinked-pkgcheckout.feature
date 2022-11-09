Feature: `osc showlinked` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
     And I execute osc with args "linkpac test:factory/test-pkgA home:Admin --force"


Scenario: Run `osc showlinked`
    When I execute osc with args "showlinked"
    Then stdout is
        """
        home:Admin/test-pkgA
        """
