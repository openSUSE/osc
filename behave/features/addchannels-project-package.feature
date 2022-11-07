Feature: `osc addchannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc addchannels <project> <package>`
    When I execute osc with args "addchannels test:factory test-pkgA"
    Then stdout is
        """
        Adding channels to package 'test:factory/test-pkgA'
        """


Scenario: Run `osc addchannels <project>/<package>`
    When I execute osc with args "addchannels test:factory/test-pkgA"
    Then stdout is
        """
        Adding channels to package 'test:factory/test-pkgA'
        """


Scenario: Run `osc addchannels <project> <package> --enable-all`
    When I execute osc with args "addchannels test:factory test-pkgA --enable-all"
    Then stdout is
        """
        Adding channels to package 'test:factory/test-pkgA' options: enable-all
        """


Scenario: Run `osc addchannels <project> <package> --skip-disabled`
    When I execute osc with args "addchannels test:factory test-pkgA --skip-disabled"
    Then stdout is
        """
        Adding channels to package 'test:factory/test-pkgA' options: skip-disabled
        """
