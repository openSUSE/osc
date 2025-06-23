Feature: `git-obs repo list` command


Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: List repos owned by an organization
    When I execute git-obs with args "repo list --org=pool"
    Then the exit code is 0
     And stdout is
        """
        pool/test-GitPkgA
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total repos: 1
        """

@destructive
Scenario: List repos owned by a user
   Given I execute git-obs with args "repo fork pool/test-GitPkgA"
    When I execute git-obs with args "repo list --user=Admin"
    Then the exit code is 0
     And stdout is
        """
        Admin/test-GitPkgA
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total repos: 1
        """


@destructive
Scenario: List repos owned by a user and an organization
   Given I execute git-obs with args "repo fork pool/test-GitPkgA"
    When I execute git-obs with args "repo list --user=Admin --org=pool"
    Then the exit code is 0
     And stdout is
        """
        pool/test-GitPkgA
        Admin/test-GitPkgA
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total repos: 2
        """

@destructive
Scenario: List repos owned by a user and an organization in json format
   Given I execute git-obs with args "repo fork pool/test-GitPkgA"
    When I execute git-obs with args "repo list --user=Admin --org=pool --export"
    Then the exit code is 0
     And stdout contains "\"owner\": \"pool\","
     And stdout contains "\"repo\": \"test-GitPkgA\","
     And stdout contains "\"owner\": \"Admin\","
     And stdout contains "\"repo\": \"test-GitPkgA\","
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): admin
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Admin


        Total repos: 2
        """
