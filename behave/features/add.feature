@no-snapshot
Feature: `osc add` command


Scenario: Run `osc add` on a new file in a package
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout openSUSE:Factory test-pkgA"
     And I set working directory to "{context.osc.temp}/openSUSE:Factory/test-pkgA"
     And I copy file "{context.fixtures}/pac/test-pkgA-1.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/new_file"
     And I execute osc with args "status --verbose"
     And stdout is
        """
        ?    new_file
             test-pkgA.changes
             test-pkgA.spec
        """
    When I execute osc with args "add new_file"
     And I execute osc with args "status --verbose"
    Then stdout is
        """
        A    new_file
             test-pkgA.changes
             test-pkgA.spec
        """
