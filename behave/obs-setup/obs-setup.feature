# This is a special feature that should be used only in kanku VM to create initial OBS configuration.
# The scenarios follow each other and there is NO CLEANUP between them.


Feature: Setup OBS.


# Using interconnect feature is a must.
# We tried to configure projects from scratch (with download-on-demand repos),
# but there are simply too many settings that must be configured properly to make it work.
#
Scenario: Create openSUSE.org project that interconnects to another OBS instance
  Given I execute osc with args "api -X PUT '/source/openSUSE.org/_meta' --file {context.fixtures}/prj/openSUSE.org.xml"
   When I execute osc with args "list"
   Then stdout is
        """
        openSUSE.org
        """


Scenario: Create openSUSE:Factory project
  Given I execute osc with args "api -X PUT '/source/openSUSE:Factory/_meta' --file {context.fixtures}/prj/openSUSE_Factory.xml"
   When I execute osc with args "list"
   Then stdout is
        """
        openSUSE.org
        openSUSE:Factory
        """


Scenario: Create home:Admin project
  Given I execute osc with args "api -X PUT '/source/home:Admin/_meta' --file {context.fixtures}/prj/home_Admin.xml"
   When I execute osc with args "list"
   Then stdout is
        """
        home:Admin
        openSUSE.org
        openSUSE:Factory
        """


Scenario: Create and build package 'test-pkgA' in 'openSUSE:Factory' project
   # checkout project
   Given I set working directory to "{context.osc.temp}"
    When I execute osc with args "checkout openSUSE:Factory"
    Then directory "{context.osc.temp}/openSUSE:Factory" exists
     And directory "{context.osc.temp}/openSUSE:Factory/.osc" exists

   # create package
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory"
    When I execute osc with args "mkpac test-pkgA"
    Then directory "{context.osc.temp}/openSUSE:Factory/test-pkgA" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgA/.osc" exists

   # add and commit new package content
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory/test-pkgA"
   # revision 1
    When I copy file "{context.fixtures}/pac/test-pkgA-1.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec"
     And I copy file "{context.fixtures}/pac/test-pkgA-1.changes" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes"
     And I execute osc with args "add test-pkgA.spec test-pkgA.changes"
     And I execute osc with args "commit -m 'Initial commit'"
   # revision 2
     And I copy file "{context.fixtures}/pac/test-pkgA-2.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec"
     And I copy file "{context.fixtures}/pac/test-pkgA-2.changes" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes"
     And I execute osc with args "commit -m 'Version 2'"
   # revision 3
     And I copy file "{context.fixtures}/pac/test-pkgA-3.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.spec"
     And I copy file "{context.fixtures}/pac/test-pkgA-3.changes" to "{context.osc.temp}/openSUSE:Factory/test-pkgA/test-pkgA.changes"
     And I execute osc with args "commit -m 'Version 3'"
    Then I wait for osc results for "openSUSE:Factory" "test-pkgA"


Scenario: Create and build package 'test-pkgB' in 'openSUSE:Factory' project
   # project checkout exists in temp already, no need to run checkout again

   # create package
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory"
    When I execute osc with args "mkpac test-pkgB"
    Then directory "{context.osc.temp}/openSUSE:Factory/test-pkgB" exists
     And directory "{context.osc.temp}/openSUSE:Factory/test-pkgB/.osc" exists

   # add and commit new package content
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory/test-pkgB"
   # revision 1
    When I copy file "{context.fixtures}/pac/test-pkgB-1.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.spec"
     And I copy file "{context.fixtures}/pac/test-pkgB-1.changes" to "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.changes"
     And I execute osc with args "add test-pkgB.spec test-pkgB.changes"
     And I execute osc with args "commit -m 'Initial commit'"
   # revision 2
     And I copy file "{context.fixtures}/pac/test-pkgB-2.spec" to "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.spec"
     And I copy file "{context.fixtures}/pac/test-pkgB-2.changes" to "{context.osc.temp}/openSUSE:Factory/test-pkgB/test-pkgB.changes"
     And I execute osc with args "commit -m 'Version 2'"
    Then I wait for osc results for "openSUSE:Factory" "test-pkgB"


Scenario: Create and build package 'multibuild-pkg' in 'openSUSE:Factory' project
   # project checkout exists in temp already, no need to run checkout again

   # create package
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory"
    When I execute osc with args "mkpac multibuild-pkg"
    Then directory "{context.osc.temp}/openSUSE:Factory/multibuild-pkg" exists
     And directory "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/.osc" exists

   # add and commit new package content
   Given I set working directory to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg"
   # revision 1
    When I copy file "{context.fixtures}/pac/multibuild-pkg-1.spec" to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/multibuild-pkg.spec"
     And I copy file "{context.fixtures}/pac/multibuild-pkg-1.changes" to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/multibuild-pkg.changes"
     And I copy file "{context.fixtures}/pac/multibuild-pkg-1._multibuild" to "{context.osc.temp}/openSUSE:Factory/multibuild-pkg/_multibuild"
     And I execute osc with args "add multibuild-pkg.spec multibuild-pkg.changes _multibuild"
     And I execute osc with args "commit -m 'Initial commit'"
    Then I wait for osc results for "openSUSE:Factory" "multibuild-pkg"
