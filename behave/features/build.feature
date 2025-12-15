Feature: `osc build` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "co test:factory/test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"


Scenario: Run `osc build --just-print-buildroot`
    When I execute osc with args "build --just-print-buildroot"
    Then the exit code is 0


Scenario: Run `osc build --alternative-project in an empty directory`
   Given I set working directory to "{context.osc.temp}"
    # we point to a spec that doesn't exist, so the command parses the arguments but fails to run the build
    When I execute osc with args "build --alternative-project=test:factory does-not-exist.spec"
    Then stdout contains "Building does-not-exist.spec for standard/x86_64"
     And the exit code is 2


Scenario: Run `osc build --alternative-project in an empty directory that has .git in the parent tree`
   Given I set working directory to "{context.osc.temp}"
     And I execute "git init -b main"
     And I create directory "{context.osc.temp}/package"
    # we point to a spec that doesn't exist, so the command parses the arguments but fails to run the build
    When I execute osc with args "build --alternative-project=test:factory does-not-exist.spec"
    Then stdout contains "Building does-not-exist.spec for standard/x86_64"
     And the exit code is 2
