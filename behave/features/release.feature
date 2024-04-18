Feature: `osc release` command


Scenario: Run `osc log` on a project
    When I execute osc with args "release test:factory --repo=standard --target-project=test:release --target-repository=distro-1-ga"
    # release target is not properly configured in the testing container, but we're currently testing only the command-line options
    Then the exit code is 1
     And stdout contains "Releasing project 'test:factory' repository 'standard' to project 'test:release' repository 'distro-1-ga' options: delayed"


Scenario: Run `osc log` on a package
    When I execute osc with args "release test:factory/test-pkgA --repo=standard --target-project=test:release --target-repository=distro-1-ga"
    Then the exit code is 0
     And stdout contains "Releasing package 'test:factory/test-pkgA' repository 'standard' to project 'test:release' repository 'distro-1-ga' options: delayed"


Scenario: Run `osc log` from a project checkout
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"
    When I execute osc with args "release --repo=standard --target-project=test:release --target-repository=distro-1-ga"
    # release target is not properly configured in the testing container, but we're currently testing only the command-line options
    Then the exit code is 1
     And stdout contains "Releasing project 'test:factory' repository 'standard' to project 'test:release' repository 'distro-1-ga' options: delayed"


Scenario: Run `osc log` from a package checkout
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
    When I execute osc with args "release --repo=standard --target-project=test:release --target-repository=distro-1-ga"
    Then the exit code is 0
     And stdout contains "Releasing package 'test:factory/test-pkgA' repository 'standard' to project 'test:release' repository 'distro-1-ga' options: delayed"


Scenario: Run `osc log` from a package checkout with a given project
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
    When I execute osc with args "release test:factory --repo=standard --target-project=test:release --target-repository=distro-1-ga"
    # release target is not properly configured in the testing container, but we're currently testing only the command-line options
    Then the exit code is 1
     And stdout contains "Releasing project 'test:factory' repository 'standard' to project 'test:release' repository 'distro-1-ga' options: delayed"
