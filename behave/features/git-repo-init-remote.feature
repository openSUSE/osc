Feature: `git-obs repo init` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "-G admin api -X POST /orgs/pool/repos --data='{{"name": "new_package"}}'"
     And I execute git-obs with args "-G admin repo clone pool/new_package --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/new_package"
     And I execute "echo '_build.*' >> .gitignore"
     And I execute "echo '*.changes merge=merge-changes' >> .gitattributes"
     And I execute "echo '[merge "merge-changes"]' >> .gitconfig"
     And I execute "echo 'driver=/usr/lib/obs/helper/bs_mergechanges %O %B %A' >> .gitconfig"
     And I execute "git add .gitignore .gitattributes .gitconfig"
     And I execute "git -c user.name=Admin -c user.email=admin@example.com commit -m 'Initial commit'"
     And I execute "git push"
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
