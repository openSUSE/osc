Feature: `osc enablechannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc enablechannels <project> <package>`
    When I execute osc with args "enablechannels test:factory test-pkgA"
    Then stdout is
        """
        Enabling channels in project: 'test:factory' package: 'test-pkgA'
        """


Scenario: Run `osc enablechannels <project>/<package>`
    When I execute osc with args "enablechannels test:factory/test-pkgA"
    Then stdout is
        """
        Enabling channels in project: 'test:factory' package: 'test-pkgA'
        """
