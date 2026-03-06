Feature: `git-obs staging group` command


Background:
   Given I set working directory to "{context.osc.temp}"

@destructive
Scenario: Warning when --fork-owner is not specified with multiple PRs
    # setup: create package PRs and then two staging project PRs
    Given I use git-obs login "alice"
      # Package PR 1
      And I execute git-obs with args "repo fork pool/test-GitPkgA"
      And I execute git-obs with args "repo clone Alice/test-GitPkgA --no-ssh-strict-host-key-checking"
      And I set working directory to "{context.osc.temp}/test-GitPkgA"
      And I execute "git checkout -b pkg1"
      And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
      And I execute "git commit -m 'v1.1' -a"
      And I execute "git push origin pkg1"
      And I execute git-obs with args "pr create --title 'Package update 1' --description='some text' --target-branch factory"
      # Package PR 2
      And I set working directory to "{context.osc.temp}"
      And I execute git-obs with args "repo fork pool/test-GitPkgB"
      And I execute git-obs with args "repo clone Alice/test-GitPkgB --no-ssh-strict-host-key-checking"
      And I set working directory to "{context.osc.temp}/test-GitPkgB"
      And I execute "git checkout factory"
      And I execute "git checkout -b pkg2"
      And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.2@' *.spec"
      And I execute "git commit -m 'v1.2' -a"
      And I execute "git push origin pkg2"
      And I execute git-obs with args "pr create --title 'Package update 2' --description='some text' --target-branch factory"
    Given I use git-obs login "admin"
      # Staging Project PR 1 (update submodule to Alice/test-GitPkgA pkg1)
      And I set working directory to "{context.osc.temp}"
      And I execute git-obs with args "repo clone openSUSE/Leap --no-ssh-strict-host-key-checking"
      And I set working directory to "{context.osc.temp}/Leap"
      And I execute "git checkout -b leap-pkgA"
      And I set env "GIT_SSH_COMMAND" to "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -i {context.fixtures}/ssh-keys/admin"
      And I execute "git submodule update --init --recursive"
      And I set working directory to "{context.osc.temp}/Leap/test-GitPkgA"
      And I execute "git remote add alice ssh://gitea@localhost:$GITEA_SERVER_SSH_PORT/Alice/test-GitPkgA.git"
      And I execute "git fetch alice pkg1"
      And I execute "git checkout FETCH_HEAD"
      And I set working directory to "{context.osc.temp}/Leap"
      And I execute "git add test-GitPkgA"
      And I execute "git commit -m 'Update test-GitPkgA submodule'"
      And I execute "git push origin leap-pkgA"
      And I execute git-obs with args "pr create --title 'Staging Group A' --description='PR: pool/test-GitPkgA!1' --target-branch factory --self"
      # Staging Project PR 2 (update submodule to Alice/test-GitPkgB pkg2)
      And I set working directory to "{context.osc.temp}/Leap"
      And I execute "git checkout factory"
      And I execute "git checkout -b leap-pkgB"
      And I set working directory to "{context.osc.temp}/Leap/test-GitPkgB"
      And I execute "git remote add alice ssh://gitea@localhost:$GITEA_SERVER_SSH_PORT/Alice/test-GitPkgB.git"
      And I execute "git fetch alice pkg2"
      And I execute "git checkout FETCH_HEAD"
      And I set working directory to "{context.osc.temp}/Leap"
      And I execute "git add test-GitPkgB"
      And I execute "git commit -m 'Update test-GitPkgB submodule'"
      And I execute "git push origin leap-pkgB"
      And I execute git-obs with args "pr create --title 'Staging Group B' --description='PR: pool/test-GitPkgB!1' --target-branch factory --self"
      # Add labels
      And I execute git-obs with args "api -X POST /repos/openSUSE/Leap/labels --data='{{"name": "staging/Backlog", "color": "ffffff"}}'"
      And I execute git-obs with args "api -X POST /repos/openSUSE/Leap/labels --data='{{"name": "staging/In Progress", "color": "afafaf"}}'"
      And I execute git-obs with args "api -X POST /repos/openSUSE/Leap/issues/1/labels --data='{{"labels": ["staging/Backlog"]}}'"
      And I execute git-obs with args "api -X POST /repos/openSUSE/Leap/issues/2/labels --data='{{"labels": ["staging/Backlog"]}}'"
    Given I use git-obs login "alice"
      When I execute git-obs with args "staging group openSUSE/Leap#1 openSUSE/Leap#2"
      Then the exit code is 0
      And stderr contains "WARNING: No fork organization specified. Defaulting to a private fork in 'Alice'."
      And I execute git-obs with args "api -X GET /repos/openSUSE/Leap/pulls/3 | jq .body"
      And stdout contains "PR: pool/test-gitpkga!1"
      And stdout contains "PR: pool/test-gitpkgb!1"