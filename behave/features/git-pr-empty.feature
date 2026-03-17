Feature: `git-obs pr create` empty pull request


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"


@destructive
Scenario: Create an empty pull request (identical commits)
    When I execute git-obs with args "pr create --title 'Empty PR' --description='no changes'"
    Then the exit code is 1
     And stderr contains "Source and target are identical"


@destructive
Scenario: Create an empty pull request with --allow-empty
    # 1. make a change and push
    Given I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
      And I execute "git commit -m 'v1.1' -a"
      And I execute "git push"
    # 2. revert the change and push
      And I execute "git revert --no-edit HEAD"
      And I execute "git push"
    # 3. try to create PR with --allow-empty
    When I execute git-obs with args "pr create --title 'Empty PR' --description='reverted changes' --allow-empty"
    Then the exit code is 0
     And stderr contains "Pull request created"
