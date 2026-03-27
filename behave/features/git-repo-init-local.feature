Feature: `git-obs repo init` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute "git init new_package"
     And I set working directory to "{context.osc.temp}/new_package"
     And I execute "echo '_build.*' >> .gitignore"
     And I execute "echo '*.changes merge=merge-changes' >> .gitattributes"
     And I execute "echo '[merge "merge-changes"]' >> .gitconfig"
     And I execute "echo 'driver=/usr/lib/obs/helper/bs_mergechanges %O %B %A' >> .gitconfig"
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Init a git repo
    # first use default local template (new_package)
    When I execute git-obs with args "repo init myNewPkg --template new_package"
    Then the exit code is 0
    When I execute "grep '_build.*' myNewPkg/.gitignore"
    Then the exit code is 0
    When I execute "grep '.changes merge=merge-changes' myNewPkg/.gitattributes"
    Then the exit code is 0
    When I execute "grep /usr/lib/obs/helper/bs_mergechanges myNewPkg/.git/config"
    Then the exit code is 0
