Feature: `osc enablechannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"


Scenario: Run `osc enablechannels`
    When I execute osc with args "enablechannels"
    Then stdout is
        """
        Enabling channels in project: 'test:factory'
        """
