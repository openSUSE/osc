Feature: Create a pull request from one fork to another fork

Background:
   Given I set working directory to "{context.osc.temp}"

@destructive
Scenario: Fork a git repo to Alice and Bob, then create a PR from Alice's fork to Bob's fork
    # Fork for Alice
    When I execute git-obs with args "-G alice repo fork pool/test-GitPkgA"
    Then the exit code is 0
     And stderr contains "Fork created: Alice/test-GitPkgA"

    # Fork for Bob
    When I execute git-obs with args "-G bob repo fork pool/test-GitPkgA"
    Then the exit code is 0
     And stderr contains "Fork created: Bob/test-GitPkgA"

    # Clone Alice's fork
    When I execute git-obs with args "-G alice repo clone Alice/test-GitPkgA --no-ssh-strict-host-key-checking"
    Then the exit code is 0

    # Change something in Alice's fork
    And I set working directory to "{context.osc.temp}/test-GitPkgA"
    And I execute "git commit -m 'Changes from Alice' --allow-empty"
    And I execute "git push"
    Then the exit code is 0

    # Create PR from Alice to Bob
    # We specify --target-owner Bob to target Bob's fork instead of the default upstream (pool)
    When I execute git-obs with args "-G alice pr create --title 'Alice to Bob PR' --description 'Please merge my changes' --target-owner Bob --target-branch=factory"
    Then the exit code is 0

    # Verify PR exists on Bob's repo
    When I execute git-obs with args "pr list Bob/test-GitPkgA"
    Then the exit code is 0
     And stdout contains "Alice to Bob PR"
     And stdout contains "Author      : Alice \(alice@example.com\)"
     And stdout contains "Source      : Alice/test-GitPkgA"
     And stdout contains "Target      : Bob/test-GitPkgA"
