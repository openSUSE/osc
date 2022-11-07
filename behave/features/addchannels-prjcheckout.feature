Feature: `osc addchannels` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"


Scenario: Run `osc addchannels`
    When I execute osc with args "addchannels"
    Then stdout is
        """
        Adding channels to project 'test:factory'
        """


Scenario: Run `osc addchannels --enable-all`
    When I execute osc with args "addchannels --enable-all"
    Then stdout is
        """
        Adding channels to project 'test:factory' options: enable-all
        """


Scenario: Run `osc addchannels --skip-disabled`
    When I execute osc with args "addchannels --skip-disabled"
    Then stdout is
        """
        Adding channels to project 'test:factory' options: skip-disabled
        """
