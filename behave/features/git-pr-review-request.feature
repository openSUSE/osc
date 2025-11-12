Feature: `git-obs pr` command

Background:
   Given I set working directory to "{context.osc.temp}"
     And I execute git-obs with args "repo fork pool/test-GitPkgA"
     And I execute git-obs with args "repo clone Admin/test-GitPkgA --no-ssh-strict-host-key-checking"
     And I set working directory to "{context.osc.temp}/test-GitPkgA"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.1@' *.spec"
     And I execute "git commit -m 'v1.1' -a"
     And I execute "sed -i 's@^\(Version: *\) .*@\1 v1.2@' *.spec"
     And I execute "git commit -m 'v1.2' -a"
     And I execute "git push"
     And I execute git-obs with args "pr create --title 'Change version' --description='some text'"
     And I execute git-obs with args "api -X POST /repos/pool/test-GitPkgA/pulls/1/requested_reviewers --data='{{"reviewers": ["bob", "alice"]}}'"

@destructive
Scenario: Check setup is correct
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout contains "bob"
    And stdout contains "alice"

@destructive
Scenario: Cancel reviews for single user
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 bob --dry-run"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout contains "bob"
    And stdout contains "alice"
    # When I execute git-obs with args "api -X DELETE /repos/pool/test-GitPkgA/pulls/1/requested_reviewers --data='{{"reviewers": ["bob"]}}'"
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 bob"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout doesn't contain "bob"
    And stdout contains "alice"
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 bob"
    Then the exit code is 1
    
@destructive
Scenario: Cancel review requests for all
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 --all --dry-run"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout contains "bob"
    And stdout contains "alice"
    # When I execute git-obs with args "api -X DELETE /repos/pool/test-GitPkgA/pulls/1/requested_reviewers --data='{{"reviewers": ["bob","alice"]}}'"
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 --all"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout doesn't contain "bob"
    And stdout doesn't contain "alice"
    
@destructive
Scenario: Cancel review requests for all with exclude lowercase
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 --all --exclude bob"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout contains "bob"
    And stdout doesn't contain "alice"
    
@destructive
Scenario: Cancel review request for all with exclude mixed case
    When I execute git-obs with args "pr review cancel-request pool/test-GitPkgA#1 --all --exclude BoB --exclude unknown"
    Then the exit code is 0
    When I execute git-obs with args "api /repos/pool/test-GitPkgA/pulls/1/reviews"
    Then the exit code is 0
    And stdout contains "bob"
    And stdout doesn't contain "alice"
