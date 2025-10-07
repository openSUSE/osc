Feature: Osc commands that do not support git


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute "git init -b factory"
     And I execute git-obs with args "meta set --apiurl='https://localhost:{context.podman.container.ports[obs_https]}' --project=test:factory --package=new-package"


Scenario: Run 'osc add'
   Given I create file "{context.osc.temp}/new-file" with perms "0644"
        """
        """
    When I execute osc with args "add new-file"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc add' is not supported with git. Use 'git add' instead.
        """


Scenario: Run 'osc addremove'
    When I execute osc with args "addremove"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc addremove' is not supported with git. Use 'git add' and 'git rm' instead.
        """


Scenario: Run 'osc branch'
    When I execute osc with args "branch"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc branch' is not supported with git. Use 'osc fork' or 'git-obs repo fork' instead.
        """


Scenario: Run 'osc checkout' to checkout a package in a git project
    # turn the git repo into a project
   Given I create file "{context.osc.temp}/_manifest" with perms "0644"
        """
        """
     And I execute git-obs with args "meta set --package="
    When I execute osc with args "checkout package"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc checkout' is not supported with git. Use 'git-obs repo clone' instead.
        """


Scenario: Run 'osc clean'
    When I execute osc with args "clean"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc clean' is not supported with git. Use 'git reset' instead.
        """


Scenario: Run 'osc commit'
    When I execute osc with args "commit"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc commit' is not supported with git. Use 'git commit' and 'git push' instead.
        """


Scenario: Run 'osc delete'
    When I execute osc with args "delete"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc delete' is not supported with git. Use 'git rm' instead.
        """


Scenario: Run 'osc deleterequest'
    When I execute osc with args "deleterequest"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc deleterequest' is not supported with git.
        """


Scenario: Run 'osc develproject'
    When I execute osc with args "develproject"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc develproject' is not supported with git.
        """


Scenario: Run 'osc diff'
    When I execute osc with args "diff"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc diff' is not supported with git. Use 'git diff' instead.
        """


Scenario: Run 'osc importsrcpkg'
    When I execute osc with args "importsrcpkg package.src.rpm"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc importsrcpkg' is not supported with git.
        """


Scenario: Run 'osc init'
    When I execute osc with args "init test:factory"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc init' is not supported with git.
        """


Scenario: Run 'osc linkpac'
    When I execute osc with args "linkpac"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc linkpac' is not supported with git.
        """


Scenario: Run 'osc linktobranch'
    When I execute osc with args "linktobranch"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc linktobranch' is not supported with git.
        """


Scenario: Run 'osc log'
    When I execute osc with args "log"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc log' is not supported with git.
        """


Scenario: Run 'osc maintainer'
    When I execute osc with args "maintainer"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc maintainer' is not supported with git.
        """


Scenario: Run 'osc maintenancerequest'
    When I execute osc with args "maintenancerequest"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc maintenancerequest' is not supported with git.
        """


Scenario: Run 'osc mkpac'
    When I execute osc with args "mkpac"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc mkpac' is not supported with git. Add a submodule with a package instead.
        """


Scenario: Run 'osc mv'
    When I execute osc with args "mv old-file new-file"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc mv' is not supported with git. Use 'git mv' instead.
        """


Scenario: Run 'osc pdiff'
    When I execute osc with args "pdiff"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc pdiff' is not supported with git.
        """


Scenario: Run 'osc pull'
    When I execute osc with args "pull"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc pull' is not supported with git. Use 'git fetch' and 'git rebase' instead.
        """


Scenario: Run 'osc releaserequest'
    When I execute osc with args "releaserequest"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc releaserequest' is not supported with git.
        """


Scenario: Run 'osc repairlink'
    When I execute osc with args "repairlink"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc repairlink' is not supported with git.
        """


Scenario: Run 'osc repairwc'
    When I execute osc with args "repairwc"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc repairwc' is not supported with git.
        """


Scenario: Run 'osc requestmaintainership'
    When I execute osc with args "requestmaintainership"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc requestmaintainership' is not supported with git.
        """


Scenario: Run 'osc resolved'
    When I execute osc with args "resolved"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc resolved' is not supported with git.
        """


Scenario: Run 'osc revert'
    When I execute osc with args "revert changed-file"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc revert' is not supported with git. Use 'git checkout' instead.
        """


Scenario: Run 'osc setdevelproject'
    When I execute osc with args "setdevelproject"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc setdevelproject' is not supported with git.
        """


Scenario: Run 'osc setlinkrev'
    When I execute osc with args "setlinkrev"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc setlinkrev' is not supported with git.
        """


Scenario: Run 'osc status'
    When I execute osc with args "status"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc status' is not supported with git. Use 'git status' instead.
        """


Scenario: Run 'osc update'
    When I execute osc with args "update"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc update' is not supported with git.
        """


Scenario: Run 'osc updatepacmetafromspec'
    When I execute osc with args "updatepacmetafromspec"
    Then the exit code is 1
     And stderr is
        """
        Command 'osc updatepacmetafromspec' is not supported with git.
        """
