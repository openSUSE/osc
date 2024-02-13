Feature: `osc setdevelproject` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Run `osc setdevelproject <project> <package> <devel_project>`
    When I execute osc with args "setdevelproject test:factory test-pkgA test:devel"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgA' to package 'test:devel/test-pkgA'
        """


@destructive
Scenario: Run `osc setdevelproject <project> <package> <devel_project> <devel_package>`
    When I execute osc with args "setdevelproject test:factory test-pkgB test:devel test-pkgA"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgB' to package 'test:devel/test-pkgA'
        """


@destructive
Scenario: Run `osc setdevelproject  <project>/<package> <devel_project>/<devel_package>`
    When I execute osc with args "setdevelproject test:factory/test-pkgB test:devel/test-pkgA"
    Then the exit code is 0
     And stdout is
        """
        Setting devel project of package 'test:factory/test-pkgB' to package 'test:devel/test-pkgA'
        """


@destructive
Scenario: Run `osc setdevelproject <project> <package> --unset`
    When I execute osc with args "setdevelproject test:factory test-pkgA --unset"
    Then the exit code is 0
     And stdout is
        """
        Unsetting devel project from package 'test:factory/test-pkgA'
        """
