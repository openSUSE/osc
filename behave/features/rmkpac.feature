Feature: `osc rmkpac` command

# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Run `osc rmkpac . <package>`
    When I execute osc with args "co home:Admin"
    Then the exit code is 0
    When I set working directory to "{context.osc.temp}/home:Admin"
    When I execute osc with args "rmkpac . test-pkgEmpty"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-pkgEmpty/_meta"
    Then the exit code is 0
    When I execute osc with args "rmkpac . test-GitPkgA --scmsync https://mygitea1.com#main"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea1.com#main"
    When I execute osc with args "rmkpac . test-GitPkgA --scmsync https://mygitea2.com#main"
    Then the exit code is 1
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea1.com#main"
    When I execute osc with args "rmkpac . test-GitPkgA --scmsync https://mygitea2.com#main --force"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea2.com#main"


@destructive
Scenario: Run `osc rmkpac <project> <package>`
    When I execute osc with args "rmkpac home:Admin ''"
    Then the exit code is 1
    When I execute osc with args "rmkpac home:Admin test-pkgEmpty"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-pkgEmpty/_meta"
    Then the exit code is 0
    When I execute osc with args "rmkpac home:Admin test-GitPkgA --scmsync https://mygitea1.com#main"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea1.com#main"
    When I execute osc with args "rmkpac home:Admin test-GitPkgA --scmsync https://mygitea2.com#main"
    Then the exit code is 1
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea1.com#main"
    When I execute osc with args "rmkpac home:Admin test-GitPkgA --scmsync https://mygitea2.com#main --force"
    Then the exit code is 0
    When I execute osc with args "api /source/home:Admin/test-GitPkgA/_meta"
    Then the exit code is 0
     And stdout contains "\<scmsync\>https://mygitea2.com#main"

@destructive
Scenario: Run `osc rmkpac <project> <package> with non-existing project'
    When I execute osc with args "rmkpac home:Admin1 test-pkgEmpty"
    Then the exit code is 1
    When I execute osc with args "rmkpac home:Admin1 test-pkgEmpty --force"
    Then the exit code is 1
    When I execute osc with args "rmkpac . test-pkgEmpty"
    Then the exit code is 1
    When I execute osc with args "rmkpac . test-pkgEmpty --force"
    Then the exit code is 1

Scenario: Run `osc rmkpac --scmsync` without fragment
    When I execute osc with args "rmkpac home:Admin test-GitPkgB --scmsync https://mygitea1.com"
    Then the exit code is 2
     And stderr contains "--scmsync must include a fragment with the branch name"
