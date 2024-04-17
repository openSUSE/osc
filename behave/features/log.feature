Feature: `osc log` command


Scenario: Run `osc log` on a package
   Given I execute osc with args "log test:factory/test-pkgA"
    Then the exit code is 0
     And stdout matches
        """
        ----------------------------------------------------------------------------
        r3 | Admin | ....-..-.. ..:..:.. | dc997133b8ddfaf084b471b05c2643b3 | 3 | 

        Version 3
        ----------------------------------------------------------------------------
        r2 | Admin | ....-..-.. ..:..:.. | 0ea55feb9cdd741ba7f523ed58a4f099 | 2 | 

        Version 2
        ----------------------------------------------------------------------------
        r1 | Admin | ....-..-.. ..:..:.. | e675755e79e0d69483d311e96d6b719e | 1 | 

        Initial commit
        ----------------------------------------------------------------------------
        """


Scenario: Run `osc log` on single revision of a package
   Given I execute osc with args "log test:factory/test-pkgA --revision=2"
    Then the exit code is 0
     And stdout matches
        """
        ----------------------------------------------------------------------------
        r2 | Admin | ....-..-.. ..:..:.. | 0ea55feb9cdd741ba7f523ed58a4f099 | 2 | 

        Version 2
        ----------------------------------------------------------------------------
        """


Scenario: Run `osc log` on revision range of a package
   Given I execute osc with args "log test:factory/test-pkgA --revision=1:2"
    Then the exit code is 0
     And stdout matches
        """
        ----------------------------------------------------------------------------
        r2 | Admin | ....-..-.. ..:..:.. | 0ea55feb9cdd741ba7f523ed58a4f099 | 2 | 

        Version 2
        ----------------------------------------------------------------------------
        r1 | Admin | ....-..-.. ..:..:.. | e675755e79e0d69483d311e96d6b719e | 1 | 

        Initial commit
        ----------------------------------------------------------------------------
        """


@wip
Scenario: Run `osc log --patch` on revision range of a package
   Given I execute osc with args "log test:factory/test-pkgA --revision=1:2 --patch"
    Then the exit code is 0
     And stdout matches
        """
        ----------------------------------------------------------------------------
        r2 \| Admin \| ....-..-.. ..:..:.. \| 0ea55feb9cdd741ba7f523ed58a4f099 \| 2 \| 

        Version 2


        changes files:
        --------------
        --- test-pkgA.changes
        \+\+\+ test-pkgA.changes
        @@ -2 \+2 @@
        -Tue Jan  4 11:22:33 UTC 2022 - Geeko Packager <email@example.com>
        \+Mon Jan  3 11:22:33 UTC 2022 - Geeko Packager <email@example.com>
        @@ -4 \+4 @@
        -- Release upstream version 2
        \+- Release upstream version 1

        spec files:
        -----------
        --- test-pkgA.spec
        \+\+\+ test-pkgA.spec
        @@ -1,5 \+1,5 @@
         Name:           test-pkgA
        -Version:        2
        \+Version:        1
         Release:        1
         License:        GPL-2.0
         Summary:        Test package

        ----------------------------------------------------------------------------
        r1 \| Admin \| ....-..-.. ..:..:.. \| e675755e79e0d69483d311e96d6b719e \| 1 \| 

        Initial commit


        changes files:
        --------------

        \+\+\+\+\+\+ deleted changes files:
        --- test-pkgA.changes

        old:
        ----
          test-pkgA.changes
          test-pkgA.spec

        spec files:
        -----------

        \+\+\+\+\+\+ deleted spec files:
        --- test-pkgA.spec


        """
