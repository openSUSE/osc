Feature: `git-obs pr` command


Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version.*\)@\1.1@' *.spec"
     And I execute "git commit -m 'Change version' -a"
     And I execute "git push"
     And I execute git-obs with args "pr create --title 'Change version' --description='some text'"


@destructive
Scenario: List pull requests
    When I execute git-obs with args "pr list pool/test-GitPkgA"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Draft       : no
        Merged      : no
        Author      : Admin \(admin@example.com\)
        Source      : Admin/test-GitPkgA, branch: factory, commit: .*
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total entries: 1
        """


@destructive
Scenario: Search pull requests
    When I execute git-obs with args "pr search"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Author      : Admin \(admin@example.com\)
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total entries: 1
        """


@destructive
Scenario: Get a pull request
    When I execute git-obs with args "pr get pool/test-GitPkgA#1"
    Then the exit code is 0
     And stdout matches
        """
        ID          : pool/test-GitPkgA#1
        URL         : http://localhost:{context.podman.container.ports[gitea_http]}/pool/test-GitPkgA/pulls/1
        Title       : Change version
        State       : open
        Draft       : no
        Merged      : no
        Author      : Admin \(admin@example.com\)
        Source      : Admin/test-GitPkgA, branch: factory, commit: .*
        Description : some text
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 1
        """


@destructive
Scenario: Get a pull request that doesn't exist
    When I execute git-obs with args "pr get does-not/exist#1"
    Then the exit code is 1
     And stdout matches
        """
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Total entries: 0
        ERROR: Couldn't retrieve the following pull requests: does-not/exist#1
        """
