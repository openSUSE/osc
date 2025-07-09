Feature: `git-obs repo init` command


Background:
   Given I set working directory to "{context.osc.temp}"

@destructive
    Scenario: Init a git repo using absolute path
    # first use remote package as a template
    When I execute git-obs with args "repo init myNewPkg --no-ssh-strict-host-key-checking"
    Then the exit code is 0
    When I execute "grep '_build.*' myNewPkg/.gitignore"
    Then the exit code is 0
    When I execute "grep '.changes merge=merge-changes' myNewPkg/.gitattributes"
    Then the exit code is 0
    When I execute "grep /usr/lib/obs/helper/bs_mergechanges myNewPkg/.git/config"

@destructive
    Scenario: Init a git repo
    # first use remote package as a template
    When I execute git-obs with args "repo init myNewPkg --template pool/test-GitPkgA --no-ssh-strict-host-key-checking"
    Then the exit code is 0
    When I execute "grep '_build.*' myNewPkg/.gitignore"
    Then the exit code is 0
    When I execute "grep '.changes merge=merge-changes' myNewPkg/.gitattributes"
    Then the exit code is 0
    When I execute "grep /usr/lib/obs/helper/bs_mergechanges myNewPkg/.git/config"
    Then the exit code is 0

