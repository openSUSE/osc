Feature: `osc fork` command


Background:
    Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Fork a git repo
    When I execute osc with args "fork test:factory test-GitPkgA"
    Then the exit code is 0
     And stdout contains " scmsync URL: "
     And stdout contains "/Admin/test-GitPkgA#factory"


@destructive
Scenario: Fork multiple git repos from different orgs
    When I execute git-obs with args "-G admin api -X POST /orgs --data '{{"username": "devel"}}'"
    When I execute osc with args "fork test:factory test-GitPkgA --target-project=test:devel --no-devel-project --gitea-fork-org=devel"
    Then the exit code is 0
     And stdout contains " scmsync URL: "
     And stdout contains "/devel/test-GitPkgA#factory"
    When I execute osc with args "fork test:factory test-GitPkgA --target-project=home:Admin --no-devel-project"
    Then the exit code is 0
     And stdout contains " scmsync URL: "
     And stdout contains "/Admin/test-GitPkgA#factory"
    When I execute osc with args "fork test:devel test-GitPkgA --target-project=home:Admin --no-devel-project"
    # there's an existing fork from a different org, the command fails
    Then the exit code is 1
    When I execute osc with args "fork test:devel test-GitPkgA --target-project=home:Admin --new-repo-name="test-GitPkgA-devel" --no-devel-project"
    Then the exit code is 0
     And stdout contains " scmsync URL: "
     And stdout contains "/Admin/test-GitPkgA-devel#factory"
