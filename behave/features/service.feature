Feature: `osc service` command


Scenario: Run `osc service manualrun`
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory test-pkgA"
     And I set working directory to "{context.osc.temp}/test:factory/test-pkgA"
     And I copy file "{context.fixtures}/pac/_service-set_version-invalid" to "{context.osc.temp}/test:factory/test-pkgA/_service"
    When I execute osc with args "service manualrun"
    Then stdout contains "Aborting: service call failed"
     And the exit code is 255
