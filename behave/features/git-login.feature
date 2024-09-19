Feature: `git-obs login` command for managing credentials entries for Gitea instances


Background:
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name    : admin
        Default : true
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Admin
        SSH Key : {context.fixtures}/ssh-keys/admin

        Name    : alice
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Alice
        SSH Key : {context.fixtures}/ssh-keys/alice

        Name    : bob
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Bob
        SSH Key : {context.fixtures}/ssh-keys/bob
        """


Scenario: Add a credentials login entry
    When I execute git-obs with args "login add example1 --url https://gitea.example.com --user Admin --token 1234"
    Then the exit code is 0
     And stderr is
         """
         Adding a Gitea credentials entry with name 'example1' ...
          * Config path: {context.osc_git.config}
         """
     And stdout is
        """
        Added entry:
        Name : example1
        URL  : https://gitea.example.com
        User : Admin
        """
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name    : admin
        Default : true
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Admin
        SSH Key : {context.fixtures}/ssh-keys/admin

        Name    : alice
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Alice
        SSH Key : {context.fixtures}/ssh-keys/alice

        Name    : bob
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Bob
        SSH Key : {context.fixtures}/ssh-keys/bob

        Name : example1
        URL  : https://gitea.example.com
        User : Admin
        """


Scenario: Remove a credentials login entry
    When I execute git-obs with args "login remove admin"
    Then the exit code is 0
     And stderr is
         """
         Removing a Gitea credentials entry with name 'admin' ...
          * Config path: {context.osc_git.config}
         """
     And stdout is
        """
        Removed entry:
        Name    : admin
        Default : true
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Admin
        SSH Key : {context.fixtures}/ssh-keys/admin
        """
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name    : alice
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Alice
        SSH Key : {context.fixtures}/ssh-keys/alice

        Name    : bob
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Bob
        SSH Key : {context.fixtures}/ssh-keys/bob
        """


Scenario: Update a credentials login entry
    When I execute git-obs with args "login update admin --new-name=NEW_NAME --new-url=NEW_URL --new-user=NEW_USER --new-token=NEW_TOKEN --new-ssh-key="
    Then the exit code is 0
     And stderr is
         """
         Updating a Gitea credentials entry with name 'admin' ...
          * Config path: {context.osc_git.config}
         """
     And stdout is
        """
        Original entry:
        Name    : admin
        Default : true
        URL     : http://localhost:{context.podman.container.ports[gitea_http]}
        User    : Admin
        SSH Key : {context.fixtures}/ssh-keys/admin

        Updated entry:
        Name    : NEW_NAME
        Default : true
        URL     : NEW_URL
        User    : NEW_USER
        """
