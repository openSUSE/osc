Feature: `git-obs staging remove` command


Background:
   Given I set working directory to "{context.osc.temp}"
     # Set GIT_SSH_COMMAND to skip host key verification for all git commands
     And I set env "GIT_SSH_COMMAND" to "ssh -o IdentitiesOnly=yes -o IdentityFile={context.fixtures}/ssh-keys/alice -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

     # Create the project repo (_ObsPrj)
     And I execute git-obs with args "-G admin api -X POST /orgs/pool/repos --data='{{"name": "_ObsPrj", "auto_init": true}}'"
     And I execute git-obs with args "-G admin api -X PUT /repos/pool/_ObsPrj/collaborators/Alice"

     # Alice clones the project repo and creates the factory branch
     And I execute git-obs with args "-G alice repo clone pool/_ObsPrj"
     And I set working directory to "{context.osc.temp}/_ObsPrj"
     And I execute "git config user.email 'alice@example.com'"
     And I execute "git config user.name 'Alice'"
     And I execute "git checkout -b factory"
     And I execute "git push origin factory"

     # Alice forks the project repo (after factory branch is created so the fork has it)
     And I execute git-obs with args "-G alice repo fork pool/_ObsPrj"

     # Create labels in the project repo
     And I execute git-obs with args "api -X POST /repos/pool/_ObsPrj/labels --data='{{"name": "staging/Backlog", "color": "#ffffff"}}'"
     And I execute git-obs with args "api -X POST /repos/pool/_ObsPrj/labels --data='{{"name": "staging/In Progress", "color": "#0000ff"}}'"

     # Alice forks and clones the package repo (test-GitPkgA)
     And I execute git-obs with args "-G alice repo fork pool/test-GitPkgA"
     And I execute git-obs with args "-G admin api -X PUT /repos/pool/test-GitPkgA/collaborators/Alice"
     And I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "-G alice repo clone pool/test-GitPkgA"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "git config user.email 'alice@example.com'"
     And I execute "git config user.name 'Alice'"

     # Alice creates a PR in test-GitPkgA
     And I execute "git checkout factory"
     And I execute "git checkout -b feature/1"
     And I execute "git commit --allow-empty -m 'feature/1'"
     And I execute "git rev-parse HEAD"
     And I search '(?P<commit>[0-9a-f]{40})' in stdout and store named groups in 'package_feature_commit'
     And I execute "git push origin feature/1"
     And I execute git-obs with args "-G alice pr create --title 'feature/1' --description='some text' --target-branch factory"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "staging/Backlog", "color": "#ffffff"}}'"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/issues/1/labels --data='{{"labels": ["staging/Backlog"]}}'"

     # Alice goes back to the project repo
     And I set working directory to "{context.osc.temp}/_ObsPrj"
     # Alice creates a staging branch in the project repo
     And I execute "git checkout factory"
     And I execute "git checkout -b staging-1"
     # Alice adds the package as a submodule
     And I execute "git submodule add ../../pool/test-GitPkgA test-GitPkgA"
     # We want the submodule to point to the commit from the feature/1 branch
     And I set working directory to "{context.osc.temp}/_ObsPrj/test-GitPkgA"
     And I execute "git fetch origin feature/1"
     And I execute "git checkout {context.package_feature_commit[0][commit]}"
     And I set working directory to "{context.osc.temp}/_ObsPrj"
     And I execute "git commit -m 'Add test-GitPkgA at feature/1' .gitmodules test-GitPkgA"
     And I execute "git push origin staging-1"

     # Alice creates the staging PR in _ObsPrj referencing test-GitPkgA#1
     And I execute git-obs with args "-G alice pr create --title 'Staging PR' --description='PR: pool/test-GitPkgA!1' --target-branch factory"
     And I search 'ID          : (?P<id>pool/_ObsPrj#(?P<number>[0-9]+))' in stdout and store named groups in 'staging_pr'


@destructive
Scenario: staging remove - remove a package PR from a staging PR
    # Verify that the staging PR is created from the parent repository, not the fork
    When I execute git-obs with args "-G alice pr get {context.staging_pr[0][id]}"
    Then stdout contains "Source      : pool/_ObsPrj"
     And stdout contains "PR: pool/test-GitPkgA!1"

    # Remove pool/test-GitPkgA#1 from the staging PR
    When I execute git-obs with args "-G alice staging remove {context.staging_pr[0][id]} pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout contains "Package pull requests have been successfully removed"

    # Verify that the staging PR no longer references pool/test-GitPkgA#1
    When I execute git-obs with args "-G alice pr get {context.staging_pr[0][id]}"
    Then stdout doesn't contain "PR: pool/test-GitPkgA!1"

    # Verify submodule is removed (because it didn't exist in factory branch)
    And I execute git-obs with args "-G alice pr checkout {context.staging_pr[0][number]}"
    And I execute "git submodule status test-GitPkgA"
    # git submodule status should fail or show nothing if submodule is removed from index
    Then the exit code is 1


@destructive
Scenario: staging remove with --close-removed
    # Remove pool/test-GitPkgA#1 from the staging PR and close pool/test-GitPkgA#1
    When I execute git-obs with args "-G alice staging remove {context.staging_pr[0][id]} pool/test-GitPkgA#1 --close-removed"
    Then the exit code is 0

    # Verify that pool/test-GitPkgA#1 is closed
    When I execute git-obs with args "-G alice pr get pool/test-GitPkgA#1"
    Then stdout contains "State       : closed"
