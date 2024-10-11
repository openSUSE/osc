Feature: `osc add` command


Scenario: Run `osc add` on a new file in a package
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
     And I create file "{context.osc.temp}/test:factory/test-pkgA/new_file" with perms "0644"
        """
        """
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
