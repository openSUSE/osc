Feature: `git-osc-precommit-hook` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I defined git-osc-precommit-hook
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
     And I execute git-obs with args "meta set --apiurl='https://localhost:{context.podman.container.ports[obs_https]}' --project=test:factory"


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

