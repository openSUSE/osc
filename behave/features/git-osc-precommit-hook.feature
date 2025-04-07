Feature: `git-osc-precommit-hook` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
     # running precommit services has a hard coded query, so openSUSE:Factory needs to exist
     And I execute osc with args "api -X PUT '/source/openSUSE:Factory/_meta' -d '<project name="openSUSE:Factory"><title></title><description></description></project>'"


@destructive
Scenario: Run git-osc-precommit-hook
    When I execute git-osc-precommit-hook with args " "
    Then the exit code is 0
     And stdout matches
        """
        """
     And stderr is
        """
        """

