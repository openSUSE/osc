Feature: `git-obs login` command for managing credentials entries for Gitea instances


Background:
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name                 : admin
        Default              : true
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Admin
        Private SSH key path : {context.fixtures}/ssh-keys/admin

        Name                 : alice
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Alice
        Private SSH key path : {context.fixtures}/ssh-keys/alice

        Name                 : bob
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Bob
        Private SSH key path : {context.fixtures}/ssh-keys/bob
        """


Scenario: Add a credentials login entry
    When I execute git-obs with args "login add example1 --url https://gitea.example.com --user Admin --token 123456789012345678901234567890abcdefabcd --set-as-default"
    Then the exit code is 0
     And stderr is
         """
         Adding a Gitea credentials entry with name 'example1' ...
          * Config path: {context.git_obs.config}
         """
     And stdout is
        """
        Added entry:
        Name                 : example1
        Default              : true
        URL                  : https://gitea.example.com
        User                 : Admin
        """
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name                 : admin
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Admin
        Private SSH key path : {context.fixtures}/ssh-keys/admin

        Name                 : alice
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Alice
        Private SSH key path : {context.fixtures}/ssh-keys/alice

        Name                 : bob
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Bob
        Private SSH key path : {context.fixtures}/ssh-keys/bob

        Name                 : example1
        Default              : true
        URL                  : https://gitea.example.com
        User                 : Admin
        """


Scenario: Remove a credentials login entry
    When I execute git-obs with args "login remove admin"
    Then the exit code is 0
     And stderr is
         """
         Removing a Gitea credentials entry with name 'admin' ...
          * Config path: {context.git_obs.config}
         """
     And stdout is
        """
        Removed entry:
        Name                 : admin
        Default              : true
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Admin
        Private SSH key path : {context.fixtures}/ssh-keys/admin
        """
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name                 : alice
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Alice
        Private SSH key path : {context.fixtures}/ssh-keys/alice

        Name                 : bob
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Bob
        Private SSH key path : {context.fixtures}/ssh-keys/bob
        """


Scenario: Update a credentials login entry
    When I execute git-obs with args "login update alice --new-name=NEW_NAME --new-url=NEW_URL --new-user=NEW_USER --new-token=1234567890123456789012345678901234567890 --new-ssh-key= --new-quiet=1 --set-as-default"
    Then the exit code is 0
     And stderr is
         """
         Updating a Gitea credentials entry with name 'alice' ...
          * Config path: {context.git_obs.config}
         """
     And stdout is
        """
        Original entry:
        Name                 : alice
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Alice
        Private SSH key path : {context.fixtures}/ssh-keys/alice

        Updated entry:
        Name                 : NEW_NAME
        Default              : true
        URL                  : NEW_URL
        User                 : NEW_USER
        Quiet                : yes
        """
    When I execute git-obs with args "login list"
    Then stdout is
        """
        Name                 : admin
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Admin
        Private SSH key path : {context.fixtures}/ssh-keys/admin

        Name                 : NEW_NAME
        Default              : true
        URL                  : NEW_URL
        User                 : NEW_USER
        Quiet                : yes

        Name                 : bob
        URL                  : http://localhost:{context.podman.container.ports[gitea_http]}
        User                 : Bob
        Private SSH key path : {context.fixtures}/ssh-keys/bob
        """
