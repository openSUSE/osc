Feature: `git-obs ssh-key` command for managing public ssh key stored in a Gitea instance


# when adding a ssh key that is already added to *any* user account, the following error pops up:
# ERROR: 422 Unprocessable Entity: b'{"message":"Key content has been used as non-deploy key","url":"http://localhost:3000/api/swagger"}\n'


Background:
    When I execute git-obs with args "ssh-key list"
    Then stdout is
        """
        ID    : 1
        Title : admin@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGo3vU8SQ9x0sdQb6gwqkCacMCB1y5LhXeETJFZpV/6J admin@gitea-test
        """


@destructive
Scenario: Add a public ssh key entry
   # to be able to use the key, we need to remove it from Bob's account first
   Given I execute git-obs with args "-G bob ssh-key remove 3"
    When I execute git-obs with args "ssh-key add --key='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIHdQ9fuh2BKeYxMqIPdIUjtToMXtBTlFegsDAPPTM8o bob@gitea-test'"
    Then the exit code is 0
     And stderr is
         """
         Using the following Gitea settings:
          * Config path: {context.git_obs.config}
          * Login (name of the entry in the config file): admin
          * URL: http://localhost:{context.podman.container.ports[gitea_http]}
          * User: Admin
         """
     And stdout is
        """
        Added entry:
        ID    : 4
        Title : bob@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIHdQ9fuh2BKeYxMqIPdIUjtToMXtBTlFegsDAPPTM8o bob@gitea-test
        """
    When I execute git-obs with args "ssh-key list"
    Then stdout is
        """
        ID    : 1
        Title : admin@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGo3vU8SQ9x0sdQb6gwqkCacMCB1y5LhXeETJFZpV/6J admin@gitea-test

        ID    : 4
        Title : bob@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIHdQ9fuh2BKeYxMqIPdIUjtToMXtBTlFegsDAPPTM8o bob@gitea-test
        """


@destructive
Scenario: Add a public ssh key entry from a .pub file
   # to be able to use the key, we need to remove it from Bob's account first
   Given I execute git-obs with args "-G bob ssh-key remove 3"
    When I execute git-obs with args "ssh-key add --key-path='{context.fixtures}/ssh-keys/bob.pub'"
    Then the exit code is 0
     And stderr is
         """
         Using the following Gitea settings:
          * Config path: {context.git_obs.config}
          * Login (name of the entry in the config file): admin
          * URL: http://localhost:{context.podman.container.ports[gitea_http]}
          * User: Admin
         """
     And stdout is
        """
        Added entry:
        ID    : 4
        Title : bob@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIHdQ9fuh2BKeYxMqIPdIUjtToMXtBTlFegsDAPPTM8o bob@gitea-test
        """
    When I execute git-obs with args "ssh-key list"
    Then stdout is
        """
        ID    : 1
        Title : admin@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGo3vU8SQ9x0sdQb6gwqkCacMCB1y5LhXeETJFZpV/6J admin@gitea-test

        ID    : 4
        Title : bob@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIHdQ9fuh2BKeYxMqIPdIUjtToMXtBTlFegsDAPPTM8o bob@gitea-test
        """


@destructive
Scenario: Try to add an invalid public ssh key
    When I execute git-obs with args "ssh-key add --key='ssh-rsa'"
    Then the exit code is 1
     And stderr is
         """
         Using the following Gitea settings:
          * Config path: {context.git_obs.config}
          * Login (name of the entry in the config file): admin
          * URL: http://localhost:{context.podman.container.ports[gitea_http]}
          * User: Admin

         ERROR: Invalid public ssh key
         """


@destructive
Scenario: Try to add an invalid public ssh key
    # key = $(echo -n secret | base64)
    When I execute git-obs with args "ssh-key add --key='ssh-rsa c2VjcmV0 admin@example.com'"
    Then the exit code is 1
     And stderr matches
         """
         Using the following Gitea settings:
          \* Config path: {context.git_obs.config}
          \* Login \(name of the entry in the config file\): admin
          \* URL: http://localhost:{context.podman.container.ports[gitea_http]}
          \* User: Admin

         ERROR: 422 Unprocessable Entity:.*Invalid key content: extractTypeFromBase64Key.*
         """


@destructive
Scenario: Remove a public ssh key entry by its id
    When I execute git-obs with args "ssh-key remove 1"
    Then stdout is
        """
        Removed entry:
        ID    : 1
        Title : admin@gitea-test
        Key   : ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGo3vU8SQ9x0sdQb6gwqkCacMCB1y5LhXeETJFZpV/6J admin@gitea-test
        """
    When I execute git-obs with args "ssh-key list"
    Then stdout is
        """
        """
