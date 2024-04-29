Feature: `osc buildinfo` command


Scenario: Run `osc buildinfo` on a package with a .inc file
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "co test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
     And I copy file "{context.fixtures}/pac/test-pkgA-3-inc.spec" to "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.spec"
     And I copy file "{context.fixtures}/pac/test-pkgA-3-inc.inc" to "{context.osc.temp}/test:factory/test-pkgA/test-pkgA.inc"
    When I execute osc with args "buildinfo"
    Then the exit code is 0
     And stdout contains "<error>unresolvable: nothing provides DOES-NOT-EXIST</error>"
