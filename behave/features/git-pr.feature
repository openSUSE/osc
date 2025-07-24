Feature: `git-obs pr` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
     And I execute "git commit -m 'v1.1' -a"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.2@' *.spec"
     And I execute "git commit -m 'v1.2' -a"
     And I execute "git push"
     And I execute git-obs with args "pr create --title 'Change version' --description='some text'"

@destructive
Scenario: List pull requests in json
    When I execute git-obs with args "pr list pool/test-GitPkgA --export"
    Then the exit code is 0
     And stdout contains "\"owner\": \"pool\","
     And stdout contains "\"repo\": \"test-GitPkgA\","
     And stdout contains "\"url\": \"http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1\""

@destructive
Scenario: List pull requests
    When I execute git-obs with args "pr list pool/test-GitPkgA"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Draft       : no
        Merged      : no
        Allow edit  : no
        Author      : Admin \(admin@example.com\)
        Source      : Admin/test-GitPkgA, branch: factory, commit: .*
        Target      : pool/test-GitPkgA, branch: factory, commit: .*
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 1
        """


@destructive
Scenario: Search pull requests
    When I execute git-obs with args "pr search"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Author      : Admin \(admin@example.com\)
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 1
        """


@destructive
Scenario: Search pull requests and print json
    When I execute git-obs with args "pr search --export"
    Then the exit code is 0
     And stdout contains "\"url\": \"http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1\""


@destructive
Scenario: Get a pull request
    When I execute git-obs with args "pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Draft       : no
        Merged      : no
        Allow edit  : no
        Author      : Admin \(admin@example.com\)
        Source      : Admin/test-GitPkgA, branch: factory, commit: .*
        Target      : pool/test-GitPkgA, branch: factory, commit: .*
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 1
        """


@destructive
Scenario: Get a pull request that doesn't exist
    When I execute git-obs with args "pr get does-not/exist#1"
    Then the exit code is 1
     And stdout matches
        """
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 0
        ERROR: Couldn't retrieve the following pull requests: does-not/exist#1
        """


@destructive
Scenario: Checkout a pull request
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking --directory=pool-test-GitPkgA"
     And I set working directory to "{context.osc.temp}/pool-test-GitPkgA"
    When I execute git-obs with args "pr checkout 1"
    Then the exit code is 0
     And stdout is
        """
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Using core.sshCommand: ssh -o IdentitiesOnly=yes -o IdentityFile={context.fixtures}/ssh-keys/admin -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
        From ssh://localhost:{context.podman.container.ports[gitea_ssh]}/Admin/test-GitPkgA
         * [new branch]      factory    -> Admin/factory
        Using core.sshCommand: ssh -o IdentitiesOnly=yes -o IdentityFile={context.fixtures}/ssh-keys/admin -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
        From ssh://localhost:{context.podman.container.ports[gitea_ssh]}/pool/test-GitPkgA
         * [new ref]         refs/pull/1/head -> pull/1
        Switched to branch 'pull/1'
        """

@destructive
Scenario: Checkout a pull request as a different user, make changes, commit, push
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking --directory=pool-test-GitPkgA -G alice"
     And I set working directory to "{context.osc.temp}/pool-test-GitPkgA"
     And I execute git-obs with args "pr checkout 1"
     And I execute git-obs with args "api -X PUT teams/1/members/alice"
     And I execute git-obs with args "pr set --allow-maintainer-edit=1 pool/test-GitPkgA#1"
    When I execute "sed -i 's@^\(Version: *\) .*@\1 v1.3@' *.spec"
     And I execute "git commit -m 'v1.3' -a"
     And I execute "git push"
    Then the exit code is 0


@destructive
Scenario: Rebase a pull request checkout to fast-forwardable changes
   # Alice makes a pull request checkout
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking --directory=alice-test-GitPkgA -G alice"
     And I set working directory to "{context.osc.temp}/alice-test-GitPkgA"
     And I execute git-obs with args "pr checkout 1"

   # Admin pushes additional changes
   Given I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v2@' *.spec"
     And I execute "git commit -m 'v2' -a"
     And I execute "git push"

   # rebase Alice's checkout to the latest Admin's changes
    When I set working directory to "{context.osc.temp}/alice-test-GitPkgA"
    # `git fetch` is required to fetch all new changes before the rebase
     And I execute "git fetch Admin"
     And I execute "git rebase"
     And I execute "git log --pretty=format:%s HEAD^^..HEAD"
    Then the exit code is 0
     And stdout is
        """
        v2
        v1.2
        """


@destructive
Scenario: Rebase a pull request checkout to non fast-forwardable changes
   # Alice makes a pull request checkout
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking --directory=alice-test-GitPkgA -G alice"
     And I set working directory to "{context.osc.temp}/alice-test-GitPkgA"
     And I execute git-obs with args "pr checkout 1"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v123@' *.spec"
     And I execute "git commit -m 'v123' -a"

   # Admin pushes a non fast-forwardable change
   Given I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "git reset --hard HEAD^"
     And I execute "git push --force"

   # rebase Alice's checkout to the latest Admin's changes
    When I set working directory to "{context.osc.temp}/alice-test-GitPkgA"
    # `git fetch` is required to fetch all new changes before the rebase
     And I execute "git fetch Admin"
     And I execute "git rebase"
     # error due to a conflicting file
     And the exit code is 1
     # --theirs refers to Alice's version of the file
     And I execute "git checkout --theirs test-GitPkgA.spec"
     And I execute "git add test-GitPkgA.spec"
     # avoid opening an editor by setting the GIT_EDITOR env variable
     And I execute "GIT_EDITOR=true git rebase --continue"
     And I execute "git log --pretty=format:%s HEAD^^..HEAD"
    Then the exit code is 0
     And stdout is
        """
        v123
        v1.1
        """


# broken due to https://github.com/go-gitea/gitea/issues/35152
# @destructive
# Scenario: Display timeline associated with a pull request
#    # change title
#    Given I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/issues/1 --data '{{"title": "NEW TITLE"}}'"
#      # add comment
#      And I execute git-obs with args "pr comment --message 'test comment' 'pool/test-GitPkgA#1'"
#      # close PR
#      And I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/issues/1 --data '{{"state": "closed"}}'"
#      # reopen PR
#      And I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/pulls/1 --data '{{"state": "open"}}'"
#      # set assignees
#      And I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/pulls/1 --data '{{"assignees": ["alice", "bob"]}}'"
#      # unset assignee
#      And I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/pulls/1 --data '{{"assignees": ["bob"]}}'"
#      # change target branch
#      And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/branches --data '{{"new_branch_name": "new-branch", "old_branch_name": "factory"}}'"
#      And I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/pulls/1 --data '{{"base": "new-branch"}}'"
#      # schedule merge
#      And I execute git-obs with args "pr merge 'pool/test-GitPkgA#1'"
#      # cancel the scheduled merge
#      And I execute git-obs with args "pr cancel-scheduled-merge 'pool/test-GitPkgA#1'"
#      # merge
#      And I execute git-obs with args "pr merge 'pool/test-GitPkgA#1' --now"
#     When I execute git-obs with args "pr get 'pool/test-GitPkgA#1' --timeline"
#     Then stdout matches
#         """
#         ID          : pool/test-GitPkgA#1
#         URL         : .*
#         Title       : NEW TITLE
#         State       : closed
#         Draft       : no
#         Merged      : yes
#         Allow edit  : no
#         Author      : Admin \(admin@example.com\)
#         Source      : Admin/test-GitPkgA, branch: factory, commit: ........................................
#         Target      : pool/test-GitPkgA, branch: new-branch, commit: ........................................
#         Description : some text
#
#         Timeline:
#         ....-..-.. ..:.. Admin pushed 2 commits
#         ....-..-.. ..:.. Admin changed title
#             \| from 'Change version' to 'NEW TITLE'
#         ....-..-.. ..:.. Admin commented
#             \| test comment
#         ....-..-.. ..:.. Admin closed the pull request
#         ....-..-.. ..:.. Admin reopened the pull request
#         ....-..-.. ..:.. Admin assigned the pull request to Alice
#         ....-..-.. ..:.. Admin assigned the pull request to Bob
#         ....-..-.. ..:.. Admin unassigned the pull request from Alice
#         ....-..-.. ..:.. Admin changed target branch from 'factory' to 'new-branch'
#         ....-..-.. ..:.. Admin scheduled the pull request to auto merge when all checks succeed
#         ....-..-.. ..:.. Admin canceled auto merging the pull request when all checks succeed
#         ....-..-.. ..:.. Admin merged commit ........................................ to new-branch
#         ....-..-.. ..:.. Admin referenced the pull request from commit
#             \| http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/commit/........................................
#             \| Merge pull request 'NEW TITLE' \(#1\) from Admin/test-GitPkgA:factory into new-branch
#          """
