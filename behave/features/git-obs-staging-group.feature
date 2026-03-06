Feature: `git-obs staging group --no-ssh-strict-host-key-checking` command

Background:
   Given I set working directory to "{context.osc.temp}"
     # it's meant to work with project pull requests, but we'll work with pool/test-GitPkgA for simplicity
     And I execute git-obs with args "-G alice repo fork pool/test-GitPkgA"
     And I execute git-obs with args "-G alice repo clone Alice/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "git config user.email 'alice@example.com'"
     And I execute "git config user.name 'Alice'"

     # Create labels
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "staging/Backlog", "color": "#ffffff"}}'"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/labels --data='{{"name": "staging/In Progress", "color": "#0000ff"}}'"

     # Alice makes a new branch feature/1, no changes on top, and makes a pull request with "PR: foo/bar!1" description
     And I execute "git checkout -b feature/1"
     And I execute "git commit --allow-empty -m 'feature/1'"
     And I execute "git push origin feature/1"
     And I execute git-obs with args "-G alice pr create --title 'feature/1' --description='PR: foo/bar!1' --target-branch factory"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/issues/1/labels --data='{{"labels": ["staging/Backlog"]}}'"

     # Alice makes a new branch feature/2, no changes on top, and makes a pull request with "PR: foo/bar!2" description
     And I execute "git checkout factory"
     And I execute "git checkout -b feature/2"
     And I execute "git commit --allow-empty -m 'feature/2'"
     And I execute "git push origin feature/2"
     And I execute git-obs with args "-G alice pr create --title 'feature/2' --description='PR: foo/bar!2' --target-branch factory"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/issues/2/labels --data='{{"labels": ["staging/Backlog"]}}'"

@destructive
Scenario: Scenario 1: staging group --no-ssh-strict-host-key-checking with --target and existing PR
    When I execute git-obs with args "-G alice staging group --no-ssh-strict-host-key-checking --target=pool/test-GitPkgA#1 pool/test-GitPkgA#2"
    Then the exit code is 0
     And stdout contains "Unable to add the 'staging/In Progress' label to pull request pool/test-GitPkgA#2"
     And stdout contains "Unable to remove the 'staging/Backlog' label from pull request pool/test-GitPkgA#2"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout contains "State       : open"
     And stdout contains "Description : PR: foo/bar!1"
     # It should also contain the reference from #2
     And stdout contains "PR: foo/bar!2"
     And stdout doesn't contain "staging/In Progress"
     And stdout contains "staging/Backlog"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#2"
    Then the exit code is 0
     And stdout contains "State       : closed"
     And stdout contains "Description : PR: foo/bar!2"

@destructive
Scenario: Scenario 2: staging group --no-ssh-strict-host-key-checking with --target and --remove-pr-references
    When I execute git-obs with args "-G alice staging group --no-ssh-strict-host-key-checking --target=pool/test-GitPkgA#1 pool/test-GitPkgA#2 --remove-pr-references"
    Then the exit code is 0
     And stdout contains "Unable to add the 'staging/In Progress' label to pull request pool/test-GitPkgA#2"
     And stdout contains "Unable to remove the 'staging/Backlog' label from pull request pool/test-GitPkgA#2"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout contains "State       : open"
     And stdout doesn't contain "staging/In Progress"
     And stdout contains "staging/Backlog"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#2"
    Then the exit code is 0
     And stdout contains "State       : closed"
     And stdout doesn't contain "PR: foo/bar!2"

@destructive
Scenario: Scenario 3: staging group --no-ssh-strict-host-key-checking without --target (creates new PR)
    When I execute git-obs with args "-G alice staging group --no-ssh-strict-host-key-checking pool/test-GitPkgA#1 pool/test-GitPkgA#2"
    Then the exit code is 0
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#3"
    Then the exit code is 0
     And stdout contains "State       : open"
     And stdout contains "PR: foo/bar!1"
     And stdout contains "PR: foo/bar!2"
     And stdout contains "Labels      : staging/In Progress"
     And stdout doesn't contain "staging/Backlog"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     # PR #1 should be closed because it was merged into #3
     And stdout contains "State       : closed"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#2"
    Then the exit code is 0
     # PR #2 should be closed because it was merged into #3
     And stdout contains "State       : closed"

@destructive
Scenario: Scenario 4: staging group --no-ssh-strict-host-key-checking without --target and --remove-pr-references
    When I execute git-obs with args "-G alice staging group --no-ssh-strict-host-key-checking pool/test-GitPkgA#1 pool/test-GitPkgA#2 --remove-pr-references"
    Then the exit code is 0
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#3"
    Then the exit code is 0
     And stdout contains "PR: foo/bar!1"
     And stdout contains "PR: foo/bar!2"
     And stdout contains "Labels      : staging/In Progress"
     And stdout doesn't contain "staging/Backlog"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout contains "State       : closed"
     And stdout doesn't contain "PR: foo/bar!1"
     And I execute git-obs with args "-G alice pr get pool/test-GitPkgA#2"
    Then the exit code is 0
     And stdout contains "State       : closed"
     And stdout doesn't contain "PR: foo/bar!2"

@destructive
Scenario: Scenario 5: staging group --no-ssh-strict-host-key-checking by another user with push permissions
     And I execute git-obs with args "-G alice api -X PUT /repos/Alice/test-GitPkgA/collaborators/Bob"
     And I set working directory to "{context.osc.temp}"
     # Bob clones Alice's fork
     And I execute git-obs with args "-G bob repo clone Alice/test-GitPkgA --directory Alice-test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/Alice-test-GitPkgA"
     And I execute "git config user.email 'bob@example.com'"
     And I execute "git config user.name 'Bob'"
    When I execute git-obs with args "-G bob staging group --no-ssh-strict-host-key-checking pool/test-GitPkgA#1 pool/test-GitPkgA#2 --fork-owner=Alice"
    Then the exit code is 0
     And I execute git-obs with args "-G bob pr get pool/test-GitPkgA#3"
    Then the exit code is 0
     And stdout contains "State       : open"
     And stdout contains "Author      : Bob \(bob@example.com\)"
     And stdout contains "PR: foo/bar!1"
     And stdout contains "PR: foo/bar!2"
     And stdout contains "Labels      : staging/In Progress"
     And stdout doesn't contain "staging/Backlog"

@destructive
Scenario: Scenario 6: staging group --no-ssh-strict-host-key-checking by another user with push permissions to the target repository
     And I execute git-obs with args "-G admin api -X PUT /repos/pool/test-GitPkgA/collaborators/Bob"
     And I set working directory to "{context.osc.temp}"
     # Bob clones the target repository
     And I execute git-obs with args "-G bob repo clone pool/test-GitPkgA --directory pool-test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/pool-test-GitPkgA"
     # Bob's git identity
     And I execute "git config user.email 'bob@example.com'"
     And I execute "git config user.name 'Bob'"
    When I execute git-obs with args "-G bob staging group --no-ssh-strict-host-key-checking pool/test-GitPkgA#1 pool/test-GitPkgA#2"
    Then the exit code is 0
     And I execute git-obs with args "-G bob pr get pool/test-GitPkgA#3"
    Then the exit code is 0
     And stdout contains "State       : open"
     # pr get output shows user login
     And stdout contains "Author      : Bob \(bob@example.com\)"
     And stdout contains "Source      : pool/test-GitPkgA"
     And stdout contains "PR: foo/bar!1"
     And stdout contains "PR: foo/bar!2"
     And stdout contains "Labels      : staging/In Progress"
     And stdout doesn't contain "staging/Backlog"
