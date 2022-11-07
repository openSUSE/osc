Feature: `osc enablechannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc enablechannels <project>`
    When I execute osc with args "enablechannels test:factory"
    Then stdout is
        """
        Enabling channels in project 'test:factory'
        """
