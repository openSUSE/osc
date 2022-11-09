Feature: `osc addcontainers` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc addcontainers <project> <package>`
    When I execute osc with args "addcontainers test:factory test-pkgA"
    Then stdout is
        """
        Adding containers to package 'test:factory/test-pkgA'
        """


Scenario: Run `osc addcontainers <project>/<package>`
    When I execute osc with args "addcontainers test:factory/test-pkgA"
    Then stdout is
        """
        Adding containers to package 'test:factory/test-pkgA'
        """


Scenario: Run `osc addcontainers <project> <package> --extend-package-names`
    When I execute osc with args "addcontainers test:factory test-pkgA --extend-package-names"
    Then stdout is
        """
        Adding containers to package 'test:factory/test-pkgA' options: extend-package-names
        """
