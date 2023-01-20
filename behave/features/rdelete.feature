Feature: `osc rdelete` command

@destructive
Scenario: Run `osc rdelete` to delete a project and mark it with a desctructive tag
   When I execute osc with args "rdelete -r -f test:factory -m 'cleanup'"
   Then the exit code is 0 
