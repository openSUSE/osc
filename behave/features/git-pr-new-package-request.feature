Feature: `git-obs pr new-package-request` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"


@destructive
Scenario: Create a new package request for current checkout
    Given I set working directory to "{context.osc.temp}/test-GitPkgA"
      And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "new/New Repository", "color": "#00ff00"}}'"
    When I execute git-obs with args "pr new-package-request --target pool/test-GitPkgA:factory"
    Then the exit code is 0
     And stderr matches
        """
        (?s).*Verifying Admin/test-GitPkgA:factory ...
        Creating request for 1 package\(s\) in pool/test-GitPkgA ...
         \* Created issue pool/test-GitPkgA#1: http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/issues/1
         \* Added label 'new/New Repository'
        """
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/issues/1"
    Then stdout contains "\"title\": \"\[ADD\] Requesting new packages in 'factory': test-GitPkgA\""
     And stdout contains "### Package Sources"
     And stdout contains "Admin/test-GitPkgA:factory"


@destructive
Scenario: Create a new package request with multiple packages and a message
    Given I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "new/New Repository", "color": "#00ff00"}}'"
    When I execute git-obs with args "pr new-package-request --target pool/test-GitPkgA:factory Admin/test-GitPkgA:factory pool/test-GitPkgA:factory -m 'Please add these'"
    Then the exit code is 0
     And stderr matches
        """
        (?s).*Verifying Admin/test-GitPkgA:factory ...
        Verifying pool/test-GitPkgA:factory ...
        Creating request for 2 package\(s\) in pool/test-GitPkgA ...
         \* Created issue pool/test-GitPkgA#1: http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/issues/1
         \* Added label 'new/New Repository'
        """
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/issues/1"
    Then stdout contains "\"title\": \"\[ADD\] Requesting new packages in 'factory': test-GitPkgA, test-GitPkgA\""
     And stdout contains "Please add these"


@destructive
Scenario: Error when target label is missing
    When I execute git-obs with args "pr new-package-request --target pool/test-GitPkgA:factory Admin/test-GitPkgA:factory"
    Then the exit code is 1
     And stderr contains "Label 'new/New Repository' doesn't exist in 'pool/test-GitPkgA'"


@destructive
Scenario: Error when package doesn't exist
    Given I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "new/New Repository", "color": "#00ff00"}}'"
    When I execute git-obs with args "pr new-package-request --target pool/test-GitPkgA:factory Admin/NonExistent:factory"
    Then the exit code is 1
     And stderr contains "Verifying Admin/NonExistent:factory ..."
     And stderr contains "ERROR: Repo 'Admin/NonExistent' does not contain branch 'factory'"
