Feature: `git-obs repo clone` command


Background:
   Given I set working directory to "{context.osc.temp}"


@destructive
Scenario: Clone a git repo
    When I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking"
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

        Cloning git repo pool/test-GitPkgA ...
        Cloning into 'test-GitPkgA'...

        Total cloned repos: 1
        """


@destructive
Scenario: Clone a git repo via http
   Given I execute git-obs with args "api -X PATCH /repos/pool/test-GitPkgA/ --data '{{"private": true}}'"
     And stdout contains ""private": true"
     And I execute git-obs with args "login update admin --new-git-uses-http=1 --new-ssh-key="
    When I set env "GIT_TERMINAL_PROMPT" to "0"
     And I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking"
    Then the exit code is 1
    Given I create file "{context.osc.temp}/gitconfig" with perms "0644"
        """
        [credential "http://localhost:{context.podman.container.ports[gitea_http]}"]
            helper = "{context.git_obs.cmd} -G admin login gitcredentials-helper"
        """
     And I set env "GIT_CONFIG_GLOBAL" to "{context.osc.temp}/gitconfig"
    When I execute git-obs with args "repo clone pool/test-GitPkgA --no-ssh-strict-host-key-checking"
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

        Cloning git repo pool/test-GitPkgA ...
        Cloning into 'test-GitPkgA'...

        Total cloned repos: 1
        """
