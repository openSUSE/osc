Feature: `osc repairwc` command


Scenario: Run `osc repairwc` on a project
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"
    When I execute osc with args "repairwc"
    Then the exit code is 0
    When I execute osc with args "status"
    Then the exit code is 0


Scenario: Run `osc repairwc` on a project without .osc/_osclib_version
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"
     And I remove file "{context.osc.temp}/test:factory/.osc/_osclib_version"
    When I execute osc with args "status"
    # assume store version 1.0 for a project
    Then the exit code is 0
     And file "{context.osc.temp}/test:factory/.osc/_osclib_version" exists


Scenario: Run `osc repairwc` on a package
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
    When I execute osc with args "repairwc"
    Then the exit code is 0
    When I execute osc with args "status"
    Then the exit code is 0


Scenario: Run `osc repairwc` on a package without .osc/_osclib_version
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
     And I remove file "{context.osc.temp}/test:factory/test-pkgA/.osc/_osclib_version"
    When I execute osc with args "status"
    Then the exit code is 1
     And file "{context.osc.temp}/test:factory/test-pkgA/.osc/_osclib_version" does not exist
    When I execute osc with args "repairwc"
    # no assumption about the store version for a package
    Then the exit code is 1
