Feature: `osc token` command


Scenario: Run `osc token` with no arguments
   When I execute osc with args "token"
   Then stdout is
        """
        <directory count="0"/>
        """


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
        <directory count="1">
          <entry id="1" string=".*" kind="rebuild" description="" triggered_at="" project="test:factory" package="test-pkgA"/>
        </directory>
        """
    And I search 'string="(?P<token>[^"]+)' in stdout and store named groups in 'tokens'
   When I execute osc with args "token --trigger {context.tokens[0][token]}"
   Then stdout is
        """
        Trigger token
        <status code="ok">
          <summary>Ok</summary>
        </status>
        """
