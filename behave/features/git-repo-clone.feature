Feature: `git-obs repo clone` command


Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Clone a git repo
    When I execute git-obs with args "repo clone pool test-GitPkgA --no-ssh-strict-host-key-checking"
    Then the exit code is 0
     And stdout is
        """
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin

        Cloning into 'test-GitPkgA'...
        """
