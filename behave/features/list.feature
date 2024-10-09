Feature: `osc list` command


Scenario: Run `osc list` with no arguments to display all projects
   When I execute osc with args "list"
   Then stdout is
        """
        home:Admin
        home:alice
        home:bob
        openSUSE.org
        test:devel
        test:factory
        test:factory:update
        test:leap:15.6
        test:leap:15.6:update
        test:release
        """


Scenario: Run `osc list` on a project to display project packages
   When I execute osc with args "list test:factory"
   Then stdout is
        """
        multibuild-pkg
        multibuild-pkg:flavor1
        multibuild-pkg:flavor2
        test-GitPkgA
        test-pkgA
        test-pkgB
        """


Scenario: Run `osc list` on a project package to display package files
   When I execute osc with args "list test:factory test-pkgA"
   Then stdout is
        """
        test-pkgA.changes
        test-pkgA.spec
        """
