@no-snapshot
Feature: `osc checkout` command


Scenario: Run `osc checkout` on a project
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory"
    Then directory "{context.osc.temp}/openSUSE:Factory" exists
     And directory "{context.osc.temp}/openSUSE:Factory/.osc" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA/.osc" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgB" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgB/.osc" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.spec" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.changes" exists


Scenario: Run `osc checkout` on a package
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory test-pkgA"
    Then directory "{context.osc.temp}/openSUSE:Factory" exists
     And directory "{context.osc.temp}/openSUSE:Factory/.osc" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA/.osc" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec" exists
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgB" does not exist


# Unlike other checkouts, file checkout doesn't create any subdirs
# and puts files directly in the working directory.
Scenario: Run `osc checkout` on a file
   Given I set working directory to "{context.osc.temp}"
   When I execute osc with args "checkout openSUSE:Factory test-pkgA test-pkgA.spec"
    Then directory "{context.osc.temp}/openSUSE:Factory" does not exist
     And file "{context.osc.temp}/test-pkgA.spec" exists
     And file "{context.osc.temp}/test-pkgA.changes" does not exist


Scenario: Run `osc checkout` on a package, use a file size limit
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory test-pkgA --limit-size=200"
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec" does not exist
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes" exists


Scenario: Run `osc checkout` on a package in a specified revision
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory test-pkgA --revision=2"
    Then file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec" is identical to "{context.fixtures}/pac/test-pkgA-2.spec"
     And file "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes" is identical to "{context.fixtures}/pac/test-pkgA-2.changes"


Scenario: Run `osc checkout` on a package, place the files in a specified output directory
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory test-pkgA --output-dir=pkgA"
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA" does not exist
     And directory "{context.osc.temp}/pkgA" exists
     And directory "{context.osc.temp}/pkgA/.osc" exists
     And file "{context.osc.temp}/pkgA/test-pkgA.spec" exists
     And file "{context.osc.temp}/pkgA/test-pkgA.changes" exists


# TODO(dmach): revisit this functionality
# Working dir becomes a project dir, package goes into a subdirectory.
# One would expect the package to go to the working dir.
Scenario: Run `osc checkout` on a package, place the files in the working directory
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory test-pkgA --current-dir"
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA" does not exist
     And directory "{context.osc.temp}/.osc" exists
     And directory "{context.osc.temp}/test-pkgA/.osc" exists
     And file "{context.osc.temp}/test-pkgA/test-pkgA.spec" exists
     And file "{context.osc.temp}/test-pkgA/test-pkgA.changes" exists
