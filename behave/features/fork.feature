Feature: `osc fork` command


Background:
    Given I set working directory to "{context.osc.temp}"

@destructive
Scenario: Fork a git repo
    When I execute osc with args "fork test:factory test-GitPkgA"
    Then the exit code is 0
     And stdout contains " scmsync URL: "
     And stdout contains "/Admin/test-GitPkgA#factory"
