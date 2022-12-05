Feature: `osc getbinaries <repo>` command from a project checkout


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout openSUSE:Factory multibuild-pkg"
     And I set working directory to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg"


Scenario: Run `osc getbinaries <repo>` from a package checkout
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg"
    When I execute osc with args "getbinaries standard"
    Then directory listing of "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-1-1.i586.rpm
        multibuild-pkg-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> --multibuild-package=<flavor>` from a package checkout
    When I execute osc with args "getbinaries standard --multibuild-package=flavor1"
    Then directory listing of "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.i586.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> --debuginfo` from a package checkout
    When I execute osc with args "getbinaries standard --debuginfo"
    Then directory listing of "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/binaries/" is
        """
        multibuild-pkg-1-1.i586.rpm
        multibuild-pkg-1-1.x86_64.rpm
        multibuild-pkg-debuginfo-1-1.i586.rpm
        multibuild-pkg-debuginfo-1-1.x86_64.rpm
        multibuild-pkg-debugsource-1-1.i586.rpm
        multibuild-pkg-debugsource-1-1.x86_64.rpm
        _buildenv
        _statistics
        rpmlint.log
        """
