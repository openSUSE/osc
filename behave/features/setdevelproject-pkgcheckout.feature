Feature: `osc setdevelproject` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


@destructive
Scenario: Run `osc setdevelproject <devel_project>`
    When I execute osc with args "setdevelproject test:devel"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgA' to project 'test:devel'
        """


@destructive
Scenario: Run `osc setdevelproject <devel_project> <devel_package>`
    When I execute osc with args "setdevelproject test:devel test-pkgA"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgA' to package 'test:devel/test-pkgA'
        """


@destructive
Scenario: Run `osc setdevelproject <devel_project>/<devel_package>`
    When I execute osc with args "setdevelproject test:devel/test-pkgA"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgA' to package 'test:devel/test-pkgA'
        """


@destructive
Scenario: Run `osc setdevelproject --unset`
   Given I execute osc with args "setdevelproject test:devel"
    When I execute osc with args "setdevelproject --unset"
    Then the exit code is 0
     And stdout is
        """
        Unsetting devel project from package 'test:factory/test-pkgA'
        """
