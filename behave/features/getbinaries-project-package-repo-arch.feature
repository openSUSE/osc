Feature: `osc getbinaries <project> <package> <repo> <arch>` command


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"


Scenario: Run `osc getbinaries <project> <package> <repo> <arch>`
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <project> <package> <repo> <arch> --multibuild-package=<flavor>`
    When I execute osc with args "getbinaries test:factory multibuild-pkg standard x86_64 --multibuild-package=flavor1"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <project> <package>:<flavor> <repo> <arch>`
    When I execute osc with args "getbinaries test:factory multibuild-pkg:flavor1 standard x86_64"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <project> <package>:<flavor> <repo> <arch> --source`
    When I execute osc with args "getbinaries test:factory multibuild-pkg:flavor1 standard x86_64 --source"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-1-1.src.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <project> <package>:<flavor> <repo> <arch> --debuginfo`
    When I execute osc with args "getbinaries test:factory multibuild-pkg:flavor1 standard x86_64 --debuginfo"
    Then directory listing of "{context.osc.temp}/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        multibuild-pkg-flavor1-debuginfo-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """
