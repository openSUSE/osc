Feature: `osc results` command


Scenario: Run `osc results` with no arguments
   When I execute osc with args "results"
   Then the exit code is 2
    And stderr is
        """
        No project given
        """


Scenario: Run `osc results <project>/<package>`
   When I execute osc with args "results test:factory/multibuild-pkg"
   Then stdout is
        """
        standard             x86_64     multibuild-pkg                 disabled
        standard             x86_64     multibuild-pkg:flavor1         disabled
        standard             x86_64     multibuild-pkg:flavor2         disabled
        standard             i586       multibuild-pkg                 disabled
        standard             i586       multibuild-pkg:flavor1         disabled
        standard             i586       multibuild-pkg:flavor2         disabled
        """


Scenario: Run `osc results` from a package checkout
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/multibuild-pkg"
     And I set working directory to "{context.osc.temp}/test:factory/multibuild-pkg"
   When I execute osc with args "results"
   Then stdout is
        """
        standard             x86_64     multibuild-pkg                 disabled
        standard             x86_64     multibuild-pkg:flavor1         disabled
        standard             x86_64     multibuild-pkg:flavor2         disabled
        standard             i586       multibuild-pkg                 disabled
        standard             i586       multibuild-pkg:flavor1         disabled
        standard             i586       multibuild-pkg:flavor2         disabled
        """


Scenario: Run `osc results <project>/<package>`, no multibuild flavors
   When I execute osc with args "results test:factory/multibuild-pkg --no-multibuild"
   Then stdout is
        """
        standard             x86_64     multibuild-pkg                 disabled
        standard             i586       multibuild-pkg                 disabled
        """


Scenario: Run `osc results` from a package checkout, multibuild flavor specified
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory/multibuild-pkg"
     And I set working directory to "{context.osc.temp}/test:factory/multibuild-pkg"
   When I execute osc with args "results -M flavor1"
   Then stdout is
        """
        standard             x86_64     multibuild-pkg:flavor1         disabled
        standard             i586       multibuild-pkg:flavor1         disabled
        """

Scenario: Run `osc results <project>/<package>`, specified output format
   When I execute osc with args "results test:factory/multibuild-pkg --format='%(repository)s|%(arch)s|%(package)s|%(code)s'"
   Then stdout is
        """
        standard|x86_64|multibuild-pkg|disabled
        standard|x86_64|multibuild-pkg:flavor1|disabled
        standard|x86_64|multibuild-pkg:flavor2|disabled
        standard|i586|multibuild-pkg|disabled
        standard|i586|multibuild-pkg:flavor1|disabled
        standard|i586|multibuild-pkg:flavor2|disabled
        """


Scenario: Run `osc results <project>/<package>`, csv output
   When I execute osc with args "results test:factory/multibuild-pkg --csv"
   Then stdout matches
        """
        "standard","x86_64","multibuild-pkg","publish.*","False","disabled",""
        "standard","x86_64","multibuild-pkg:flavor1","publish.*","False","disabled",""
        "standard","x86_64","multibuild-pkg:flavor2","publish.*","False","disabled",""
        "standard","i586","multibuild-pkg","publish.*","False","disabled",""
        "standard","i586","multibuild-pkg:flavor1","publish.*","False","disabled",""
        "standard","i586","multibuild-pkg:flavor2","publish.*","False","disabled",""
        """


Scenario: Run `osc results <project>/<package>`, csv output, multibuild flavor specified
   When I execute osc with args "results test:factory/multibuild-pkg --csv -M flavor1"
   Then stdout matches
        """
        "standard","x86_64","multibuild-pkg:flavor1","publish.*","False","disabled",""
        "standard","i586","multibuild-pkg:flavor1","publish.*","False","disabled",""
        """


Scenario: Run `osc results <project>/<package>`, csv output, specified output format (columns)
   When I execute osc with args "results test:factory/multibuild-pkg --csv --format='repository,arch,package,code'"
   Then stdout is
        """
        "standard","x86_64","multibuild-pkg","disabled"
        "standard","x86_64","multibuild-pkg:flavor1","disabled"
        "standard","x86_64","multibuild-pkg:flavor2","disabled"
        "standard","i586","multibuild-pkg","disabled"
        "standard","i586","multibuild-pkg:flavor1","disabled"
        "standard","i586","multibuild-pkg:flavor2","disabled"
        """


Scenario: Run `osc results <project>/<package>`, xml output
   When I execute osc with args "results test:factory/multibuild-pkg --xml"
   Then stdout matches
        """
        <resultlist state=".*">
          <result project="test:factory" repository="standard" arch="x86_64" code="publish.*" state="publish.*">
            <status package="multibuild-pkg" code="disabled"/>
            <status package="multibuild-pkg:flavor1" code="disabled"/>
            <status package="multibuild-pkg:flavor2" code="disabled"/>
          </result>
          <result project="test:factory" repository="standard" arch="i586" code="publish.*" state="publish.*">
            <status package="multibuild-pkg" code="disabled"/>
            <status package="multibuild-pkg:flavor1" code="disabled"/>
            <status package="multibuild-pkg:flavor2" code="disabled"/>
          </result>
        </resultlist>
        """


Scenario: Run `osc results <project>/<package>`, xml output, multibuild flavor specified
   When I execute osc with args "results test:factory/multibuild-pkg --xml -M flavor1"
   Then stdout matches
        """
        <resultlist state=".*">
          <result project="test:factory" repository="standard" arch="x86_64" code="publish.*" state="publish.*">
            <status package="multibuild-pkg:flavor1" code="disabled" />
          </result>
          <result project="test:factory" repository="standard" arch="i586" code="publish.*" state="publish.*">
            <status package="multibuild-pkg:flavor1" code="disabled" />
          </result>
        </resultlist>
        """
