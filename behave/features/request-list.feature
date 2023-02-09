Feature: `osc request list` command


Scenario: Run `osc request list` on a project
   When I execute osc with args "request list -P test:factory"
   Then the exit code is 0 
