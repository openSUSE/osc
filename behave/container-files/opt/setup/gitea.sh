set -x
set -e


TOPDIR=$(dirname $(readlink -f "$0"))
source "$TOPDIR/common.sh"


OSC="osc -A https://localhost"


chown gitea:gitea /etc/gitea/conf/app.ini

DB_PATH=/var/lib/gitea/data/gitea.db

# create the database
su - gitea -c 'gitea migrate'


# to generate an access token for testing, use the following Python code:
#       from hashlib import pbkdf2_hmac
#       char = b"1"
#       print(pbkdf2_hmac(hash_name="sha256", password=40*char, salt=10*char, iterations=10000, dklen=50).hex())


# user #1: Admin, password=opensuse
# gitea refuses to create user 'admin'; let's create 'admin1' and rename it in the database
su - gitea -c 'gitea admin user create --username Admin1 --password opensuse --email admin@example.com --must-change-password=false --admin'
su - gitea -c "echo \"update user set lower_name='admin', name='Admin' where lower_name = 'admin1';\" | sqlite3 $DB_PATH"
su - gitea -c "echo \"INSERT INTO access_token (uid, name, token_hash, token_salt, token_last_eight, scope, created_unix, updated_unix) VALUES (1, 'admin', '2da98f9cae724ae30563e3ba9663afb24af91019d04736523f1762eed291c449aebbbb749571958e1811588b33e64ae86bd7', '1111111111', '11111111', 'all', 0, 0);\" | sqlite3 $DB_PATH"
export TOKEN_ADMIN='1111111111111111111111111111111111111111'


# user #2: Alice, password=opensuse
su - gitea -c 'gitea admin user create --username Alice --password opensuse --email alice@example.com --must-change-password=false'
#su - gitea -c "echo \"update user set must_change_password=0 where lower_name = 'alice';\" | sqlite3 $DB_PATH"
su - gitea -c "echo \"INSERT INTO access_token (uid, name, token_hash, token_salt, token_last_eight, scope, created_unix, updated_unix) VALUES (2, 'alice', '5aeaf57e2c156673a566815b5a5739f9aa25bc3ac0a3c9e942f31361230e1f26983f6b2abfd009358202fc2e02c8137693ee', 'aaaaaaaaaa', 'aaaaaaaa', 'all', 0, 0);\" | sqlite3 $DB_PATH"
export TOKEN_ALICE='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

#sqlite> update access_token set scope='read:repository,write:repository,read:user' where id in (2,3);
#read:issue

# user #3 Bob, password=opensuse
su - gitea -c 'gitea admin user create --username Bob --password opensuse --email bob@example.com --must-change-password=false'
#su - gitea -c "echo \"update user set must_change_password=0 where lower_name = 'bob';\" | sqlite3 $DB_PATH"
su - gitea -c "echo \"INSERT INTO access_token (uid, name, token_hash, token_salt, token_last_eight, scope, created_unix, updated_unix) VALUES (3, 'bob', 'b97a745cff7dabb6a767c4e993609ef41c54b8f722f9ff88b4232430e087751d54436fec1240f056585b270f432efb02d188', 'bbbbbbbbbb', 'bbbbbbbb', 'all', 0, 0);\" | sqlite3 $DB_PATH"
export TOKEN_BOB='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'


systemctl enable gitea
systemctl enable gitea-configure-from-env
systemctl enable gitea-fix-var-lib-gitea-data


su - gitea -c 'gitea' 2>&1 >/dev/null &
sleep 15


function create_org {
    org="$1"
    curl \
        -X POST \
        -H "Authorization: token $TOKEN_ADMIN" \
        -H "Content-type: application/json" \
        --data "{\"username\": \"$org\"}" \
        "http://localhost:3000/api/v1/orgs"
}


function create_org_repo {
    org="$1"
    repo="$2"
    branch="${3:-factory}"
    curl \
        -X POST \
        -H "Authorization: token $TOKEN_ADMIN" \
        -H "Content-type: application/json" \
        --data "{\"name\": \"$repo\", \"default_branch\": \"$branch\"}" \
        "http://localhost:3000/api/v1/orgs/$org/repos"
}


function add_ssh_key {
    user="$1"
    token="$2"
    ssh_key_path="$3"

    key="$(cat $ssh_key_path)"
    curl \
        -X POST \
        -H "Authorization: token $token" \
        -H "Content-type: application/json" \
        --data "{\"key\": \"$key\", \"title\": \"$(echo $key | cut -d ' ' -f 3-)\"}" \
        "http://localhost:3000/api/v1/user/keys"
}


create_org pool
create_org_repo pool new_package main
create_org_repo pool test-GitPkgA
add_ssh_key admin $TOKEN_ADMIN /root/.ssh/admin.pub
add_ssh_key alice $TOKEN_ALICE /root/.ssh/alice.pub
add_ssh_key bob $TOKEN_BOB /root/.ssh/bob.pub

# create pool/new_package to use in `git repo init`
(
GITDIR="$(mktemp -d)"
cd "$GITDIR"

git init --initial-branch main
# git commiter equals to the configured user
git config user.name "Geeko Packager"
git config user.email "email@example.com"

echo '_build.*' >> .gitignore
echo '*.changes merge=merge-changes' >> .gitattributes
echo '[merge "merge-changes"]' >> .gitconfig
echo 'driver=/usr/lib/obs/helper/bs_mergechanges %O %B %A' >> .gitconfig

git add * .gitignore .gitattributes .gitconfig
DATE="2022-01-03 11:22:33 UTC"
GIT_COMMITTER_DATE="$DATE" git commit -a -m "Initial commit" --date "$DATE"

echo AAA > testfile

git add *
DATE="2022-01-04 11:22:33 UTC"
GIT_COMMITTER_DATE="$DATE" git commit -a -m "Initial commit2" --date "$DATE"


git remote add origin http://admin:opensuse@localhost:3000/pool/new_package.git
git push --set-upstream origin main
)


# create test-GitPkgA package based on test-PkgA
# * change the package name
# * use changelog dates as commit/commiter dates for reproducibility

GITDIR="$(mktemp -d)"
pushd "$GITDIR"

git init --initial-branch factory
# git commiter equals to the configured user
git config user.name "Geeko Packager"
git config user.email "email@example.com"

cp -a "$TOPDIR"/fixtures/pac/test-pkgA-1.spec test-GitPkgA.spec
cp -a "$TOPDIR"/fixtures/pac/test-pkgA-1.changes test-GitPkgA.changes
sed 's@test-pkgA@test-GitPkgA@' -i *

echo '_build.*' >> .gitignore
echo '*.changes merge=merge-changes' >> .gitattributes
echo '[merge "merge-changes"]' >> .gitconfig
echo 'driver=/usr/lib/obs/helper/bs_mergechanges %O %B %A' >> .gitconfig

git add * .gitignore .gitattributes .gitconfig
DATE="2022-01-03 11:22:33 UTC"
GIT_COMMITTER_DATE="$DATE" git commit -a -m "Initial commit" --date "$DATE"

cp -a "$TOPDIR"/fixtures/pac/test-pkgA-2.spec test-GitPkgA.spec
cp -a "$TOPDIR"/fixtures/pac/test-pkgA-2.changes test-GitPkgA.changes
sed 's@test-pkgA@test-GitPkgA@' -i *
git add *
DATE="2022-01-04 11:22:33 UTC"
GIT_COMMITTER_DATE="$DATE" git commit -a -m "Version 2" --date "$DATE"

cp -a "$TOPDIR"/fixtures/pac/test-pkgA-3.spec test-GitPkgA.spec
cp -a "$TOPDIR"/fixtures/pac/test-pkgA-3.changes test-GitPkgA.changes
sed 's@test-pkgA@test-GitPkgA@' -i *
git add *
DATE="2022-01-05 11:22:33 UTC"
GIT_COMMITTER_DATE="$DATE" git commit -a -m "Version 3" --date "$DATE"

git remote add origin http://admin:opensuse@localhost:3000/pool/test-GitPkgA.git
git push --set-upstream origin factory

popd

# create test-GitPkgA package in test:factory that has scmsync set to gitea
$OSC api -X PUT '/source/test:factory/test-GitPkgA/_meta' --file "$TOPDIR"/fixtures/pac/test-GitPkgA.xml


# gitea-action-runner
systemctl enable podman.socket
systemctl enable gitea-action-runner.service

# auth token for action runners
export TOKEN_ACT_RUNNER="rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr"
su - gitea -c "echo \"INSERT INTO action_runner_token (token, owner_id, repo_id, is_active) VALUES ('$TOKEN_ACT_RUNNER', 0, 0, 1);\" | sqlite3 $DB_PATH"

# gitea-action-runner.service requires .runner file in this location
pushd /var/lib/gitea-action-runner
gitea-action-runner register --no-interactive --instance http://localhost:3000 --token=$TOKEN_ACT_RUNNER
# localhost in the container spawned by the gitea action runner is different than the localhost gitea is running in
# so we need to redirect the address to the parent container
sed -i 's@"address": ".*"@"address": "http://host.containers.internal:3000"@' .runner
