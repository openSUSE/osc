Feature: `osc addcontainers` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc addcontainers`
    When I execute osc with args "addcontainers"
    Then stdout is
        """
        Adding containers to package 'test:factory/test-pkgA'
        """


Scenario: Run `osc addcontainers --extend-package-names`
    When I execute osc with args "addcontainers --extend-package-names"
    Then stdout is
        """
        Adding containers to package 'test:factory/test-pkgA' options: extend-package-names
        """
