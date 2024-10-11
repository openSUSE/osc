Feature: `git-obs repo fork` command


Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Fork a git repo
    When I execute git-obs with args "repo fork pool test-GitPkgA"
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

        Forking git repo pool/test-GitPkgA ...
         * Fork created: Admin/test-GitPkgA
        """


@destructive
Scenario: Fork a git repo twice under different names
    When I execute git-obs with args "repo fork pool test-GitPkgA"
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

        Forking git repo pool/test-GitPkgA ...
         * Fork created: Admin/test-GitPkgA
        """
    When I execute git-obs with args "repo fork pool test-GitPkgA --new-repo-name=new-package"
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

        Forking git repo pool/test-GitPkgA ...
         * Fork already exists: Admin/test-GitPkgA
         * WARNING: Using an existing fork with a different name than requested
        """


@destructive
Scenario: Fork a git repo from pool and fork someone else's fork of the same repo
    When I execute git-obs with args "repo fork pool test-GitPkgA"
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

        Forking git repo pool/test-GitPkgA ...
         * Fork created: Admin/test-GitPkgA
        """
    When I execute git-obs with args "repo fork -G alice pool test-GitPkgA --new-repo-name=test-GitPkgA-alice"
    Then the exit code is 0
     And stdout is
        """
        """
     And stderr is
        """
        Using the following Gitea settings:
         * Config path: {context.git_obs.config}
         * Login (name of the entry in the config file): alice
         * URL: http://localhost:{context.podman.container.ports[gitea_http]}
         * User: Alice

        Forking git repo pool/test-GitPkgA ...
         * Fork created: Alice/test-GitPkgA-alice
        """
    # this succeeds with 202 and the requested fork is NOT created
    When I execute git-obs with args "repo fork Alice test-GitPkgA-alice"
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

        Forking git repo Alice/test-GitPkgA-alice ...
         * Fork created: Admin/test-GitPkgA-alice
        """
    When I execute git-obs with args "repo clone Admin test-GitPkgA-alice --no-ssh-strict-host-key-checking"
    Then the exit code is 0
