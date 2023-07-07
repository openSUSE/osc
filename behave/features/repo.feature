Feature: `osc repo` command


Scenario: Run `osc repo` with no arguments
   When I execute osc with args "repo"
   Then stdout is
        """
        """


Scenario: Run `osc repo list` on a project
   When I execute osc with args "repo list test:factory"
   Then stdout is
        """
        Repository    : standard
        Architectures : x86_64, i586
        Paths         : openSUSE.org:openSUSE:Tumbleweed/standard
        Flags
            build     : disable: x86_64, i586
        """


@destructive
Scenario: Run `osc repo add` on a project
   When I execute osc with args "repo add --yes test:factory --repo=new-repo --arch=x86_64 --arch=aarch64 --path=test:factory/standard --path=test:devel/standard"
    And I execute osc with args "repo list test:factory"
   Then stdout is
        """
        Repository    : standard
        Architectures : x86_64, i586
        Paths         : openSUSE.org:openSUSE:Tumbleweed/standard
        Flags
            build     : disable: x86_64, i586

        Repository    : new-repo
        Architectures : x86_64, aarch64
        Paths         : test:factory/standard
                        test:devel/standard
        Flags
            build     : disable: x86_64, aarch64
        """


@destructive
Scenario: Run `osc repo remove` on a project
   When I execute osc with args "repo remove --yes test:factory --repo=standard --repo=does-not-exist"
    And I execute osc with args "repo list test:factory"
   Then stdout is
        """
        """
