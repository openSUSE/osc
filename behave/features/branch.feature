Feature: `osc branch` command


@destructive
Scenario: Run `osc branch` on an inherited package that has no devel project set
    When I execute osc with args "branch test:leap:15.6:update/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:leap:15.6/test-pkgA/_link"
     And stdout contains "<link project=\"test:leap:15.6\""


@destructive
Scenario: Run `osc branch --nodevelproject` on an inherited package that has no devel project set
    When I execute osc with args "branch test:leap:15.6:update/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:leap:15.6/test-pkgA/_link"
     And stdout contains "<link project=\"test:leap:15.6\""


@destructive
Scenario: Run `osc branch --new-package` on an inherited package that has no devel project set
    When I execute osc with args "branch --new-package test:leap:15.6:update/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:leap:15.6:update/test-pkgA/_link"
     And stdout contains "<link project=\"test:leap:15.6:update\""


@destructive
Scenario: Run `osc branch` on a package that has a devel project set
    When I execute osc with args "branch test:factory/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:devel/test-pkgA/_link"
     And stdout contains "<link project=\"test:devel\""


@destructive
Scenario: Run `osc branch --nodevelproject` on a package that has a devel project set
    When I execute osc with args "branch --nodevelproject test:factory/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:factory/test-pkgA/_link"
     And stdout contains "<link project=\"test:factory\""


@destructive
Scenario: Run `osc branch` on an inherited  package that has a devel project set
    When I execute osc with args "branch test:factory:update/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:devel/test-pkgA/_link"
     And stdout contains "<link project=\"test:devel\""


@destructive
Scenario: Run `osc branch --nodevelproject` on an inherited package that has a devel project set
    When I execute osc with args "branch --nodevelproject test:factory:update/test-pkgA"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:factory/test-pkgA/_link"
     And stdout contains "<link project=\"test:factory\""


@destructive
Scenario: Run `osc branch --new-package` on a package that doesn't exist
    When I execute osc with args "branch --new-package test:factory/test-pkgNEW"
    Then the exit code is 0
     And I execute osc with args "api /source/home:Admin:branches:test:factory/test-pkgNEW/_link"
     And stdout contains "<link project=\"test:factory\""
