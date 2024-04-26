Feature: `osc token` command


Scenario: Run `osc token` with no arguments
   When I execute osc with args "token"
   Then stdout is
        """
        """


@destructive
Scenario: Run `osc token --operation rebuild`
   When I execute osc with args "token --create --operation rebuild test:factory test-pkgA"
   Then stdout matches
        """
        Create a new token
        <status code="ok">
          <summary>Ok</summary>
          <data name="token">.*</data>
          <data name="id">1</data>
        </status>
        """
  Given I execute osc with args "token"
    And stdout matches
        """
        ID           : 1
        String       : .*
        Operation    : rebuild
        Description  : 
        Project      : test:factory
        Package      : test-pkgA
        Triggered at : 
        """
    And I search 'String *: *(?P<token>.+)\n' in stdout and store named groups in 'tokens'
   When I execute osc with args "token --trigger {context.tokens[0][token]}"
   Then stdout is
        """
        Trigger token
        <status code="ok">
          <summary>Ok</summary>
        </status>
        """
