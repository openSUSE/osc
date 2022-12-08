Feature: `osc getbinaries <repo> <arch>` command from a package checkout


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory multibuild-pkg"
     And I set working directory to "{context.osc.temp}/test:factory/multibuild-pkg"


Scenario: Run `osc getbinaries <repo> <arch>` from a package checkout
    When I execute osc with args "getbinaries standard x86_64"
    Then directory listing of "{context.osc.temp}/test:factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> <arch> --multibuild-package=<flavor>` from a package checkout
    When I execute osc with args "getbinaries standard x86_64 --multibuild-package=flavor1"
    Then directory listing of "{context.osc.temp}/test:factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> <arch> --debuginfo` from a package checkout
    When I execute osc with args "getbinaries standard x86_64 --debuginfo"
    Then directory listing of "{context.osc.temp}/test:factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-1-1.x86_64.rpm
        multibuild-pkg-debuginfo-1-1.x86_64.rpm
        multibuild-pkg-debugsource-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """
