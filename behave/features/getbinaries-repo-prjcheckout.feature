Feature: `osc getbinaries <repo>` command from a project checkout


# common steps for all scenarios
Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute osc with args "checkout test:factory"
     And I set working directory to "{context.osc.temp}/test:factory"


Scenario: Run `osc getbinaries <repo>` from a project checkout
    When I execute osc with args "getbinaries standard"
    Then directory tree in "{context.osc.temp}/test:factory/binaries/" is
        """
        multibuild-pkg-1-1.i586.rpm
        multibuild-pkg-1-1.x86_64.rpm
        multibuild-pkg-flavor1-1-1.i586.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        multibuild-pkg-flavor2-1-1.i586.rpm
        multibuild-pkg-flavor2-1-1.x86_64.rpm
        test-pkgA-3-1.noarch.rpm
        test-pkgB-2-1.noarch.rpm
        multibuild-pkg/_buildenv
        multibuild-pkg/_statistics
        multibuild-pkg/rpmlint.log
        multibuild-pkg:flavor1/_buildenv
        multibuild-pkg:flavor1/_statistics
        multibuild-pkg:flavor1/rpmlint.log
        multibuild-pkg:flavor2/_buildenv
        multibuild-pkg:flavor2/_statistics
        multibuild-pkg:flavor2/rpmlint.log
        test-pkgA/_buildenv
        test-pkgA/_statistics
        test-pkgA/rpmlint.log
        test-pkgB/_buildenv
        test-pkgB/_statistics
        test-pkgB/rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> --multibuild-package=<flavor>` from a project checkout
    When I execute osc with args "getbinaries standard --multibuild-package=flavor1"
    Then directory tree in "{context.osc.temp}/test:factory/binaries/" is
        """
        multibuild-pkg-flavor1-1-1.i586.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        multibuild-pkg:flavor1/_buildenv
        multibuild-pkg:flavor1/_statistics
        multibuild-pkg:flavor1/rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> --sources` from a project checkout
    When I execute osc with args "getbinaries standard --sources"
    Then directory tree in "{context.osc.temp}/test:factory/binaries/" is
        """
        multibuild-pkg-1-1.i586.rpm
        multibuild-pkg-1-1.src.rpm
        multibuild-pkg-1-1.x86_64.rpm
        multibuild-pkg-1-1.src.rpm
        multibuild-pkg-flavor1-1-1.i586.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        multibuild-pkg-1-1.src.rpm
        multibuild-pkg-flavor2-1-1.i586.rpm
        multibuild-pkg-flavor2-1-1.x86_64.rpm
        test-pkgA-3-1.noarch.rpm
        test-pkgA-3-1.src.rpm
        test-pkgB-2-1.noarch.rpm
        test-pkgB-2-1.src.rpm
        multibuild-pkg/_buildenv
        multibuild-pkg/_statistics
        multibuild-pkg/rpmlint.log
        multibuild-pkg:flavor1/_buildenv
        multibuild-pkg:flavor1/_statistics
        multibuild-pkg:flavor1/rpmlint.log
        multibuild-pkg:flavor2/_buildenv
        multibuild-pkg:flavor2/_statistics
        multibuild-pkg:flavor2/rpmlint.log
        test-pkgA/_buildenv
        test-pkgA/_statistics
        test-pkgA/rpmlint.log
        test-pkgB/_buildenv
        test-pkgB/_statistics
        test-pkgB/rpmlint.log
        """


Scenario: Run `osc getbinaries <repo> --debuginfo` from a project checkout
    When I execute osc with args "getbinaries standard --debuginfo"
    Then directory tree in "{context.osc.temp}/test:factory/binaries/" is
        """
        multibuild-pkg-1-1.i586.rpm
        multibuild-pkg-1-1.x86_64.rpm
        multibuild-pkg-debuginfo-1-1.i586.rpm
        multibuild-pkg-debuginfo-1-1.x86_64.rpm
        multibuild-pkg-debugsource-1-1.i586.rpm
        multibuild-pkg-debugsource-1-1.x86_64.rpm
        multibuild-pkg-flavor1-1-1.i586.rpm
        multibuild-pkg-flavor1-1-1.x86_64.rpm
        multibuild-pkg-flavor1-debuginfo-1-1.i586.rpm
        multibuild-pkg-flavor1-debuginfo-1-1.x86_64.rpm
        multibuild-pkg-flavor2-1-1.i586.rpm
        multibuild-pkg-flavor2-1-1.x86_64.rpm
        multibuild-pkg-flavor2-debuginfo-1-1.i586.rpm
        multibuild-pkg-flavor2-debuginfo-1-1.x86_64.rpm
        test-pkgA-3-1.noarch.rpm
        test-pkgB-2-1.noarch.rpm
        multibuild-pkg/_buildenv
        multibuild-pkg/_statistics
        multibuild-pkg/rpmlint.log
        multibuild-pkg:flavor1/_buildenv
        multibuild-pkg:flavor1/_statistics
        multibuild-pkg:flavor1/rpmlint.log
        multibuild-pkg:flavor2/_buildenv
        multibuild-pkg:flavor2/_statistics
        multibuild-pkg:flavor2/rpmlint.log
        test-pkgA/_buildenv
        test-pkgA/_statistics
        test-pkgA/rpmlint.log
        test-pkgB/_buildenv
        test-pkgB/_statistics
        test-pkgB/rpmlint.log
        """
