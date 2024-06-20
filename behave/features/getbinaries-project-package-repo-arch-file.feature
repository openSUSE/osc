Feature: `osc getbinaries <project> <package> <repo> <arch> <file>` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file>`
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-1-1.x86_64.rpm"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-1-1.x86_64.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file> --multibuild-package=<flavor>`
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-flavor1-1-1.x86_64.rpm --multibuild-package=flavor1"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        """


Scenario: Run `osc getbinaries <project> <package>:<flavor> <repo> <arch> <file>` where file is a package
    When I execute osc with args "getbinaries test:factory multibuild-pkg:flavor1 standard x86_64 multibuild-pkg-flavor1-1-1.x86_64.rpm"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file>` where file is a source package
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-1-1.src.rpm"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-1-1.src.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file> --source` where file is a source package
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-1-1.src.rpm --source"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-1-1.src.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file>` where file is a debuginfo package
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-debuginfo-1-1.x86_64.rpm"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-debuginfo-1-1.x86_64.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file> --debuginfo` where file is a debuginfo package
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 multibuild-pkg-debuginfo-1-1.x86_64.rpm --debuginfo"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-debuginfo-1-1.x86_64.rpm
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> <file>` where file is a log file
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 rpmlint.log"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        rpmlint.log
        """
