Feature: `osc addchannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc addchannels <project>`
    When I execute osc with args "addchannels test:factory"
    Then stdout is
        """
        Adding channels to project: 'test:factory'
        """


Scenario: Run `osc addchannels <project> --enable-all`
    When I execute osc with args "addchannels test:factory --enable-all"
    Then stdout is
        """
        Adding channels to project: 'test:factory' options: enable-all
        """


Scenario: Run `osc addchannels <project> --skip-disabled`
    When I execute osc with args "addchannels test:factory --skip-disabled"
    Then stdout is
        """
        Adding channels to project: 'test:factory' options: skip-disabled
        """

