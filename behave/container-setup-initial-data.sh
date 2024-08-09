set -x
set -e


TOPDIR=$(dirname $(readlink -f "$0"))
source "$TOPDIR/container-setup-common.sh"


start_mysql
start_apache
start_obs_srcserver
sleep 1


FIXTURES_DIR="$TOPDIR/fixtures"
OSC="osc -A https://localhost"

# create additional users
$OSC person register --login=alice --realname='' --email='alice@example.com' --password='opensuse'
$OSC person register --login=bob --realname='' --email='bob@example.com' --password='opensuse'

# create projects
$OSC api -X PUT '/source/openSUSE.org/_meta' --file "$FIXTURES_DIR/prj/openSUSE.org.xml"
$OSC api -X PUT '/source/test:devel/_meta' --file "$FIXTURES_DIR/prj/test_devel.xml"

# test:factory:update inherits from test:factory; test:factory has test:devel devel project
$OSC api -X PUT '/source/test:factory/_meta' --file "$FIXTURES_DIR/prj/test_factory.xml"
$OSC api -X PUT '/source/test:factory:update/_meta' --file "$FIXTURES_DIR/prj/test_factory_update.xml"

# test:leap:15.6:update inherits from test:leap:15.6; test:leap:15.6 has no devel project
$OSC api -X PUT '/source/test:leap:15.6/_meta' --file "$FIXTURES_DIR/prj/test_leap_15.6.xml"
$OSC api -X PUT '/source/test:leap:15.6:update/_meta' --file "$FIXTURES_DIR/prj/test_leap_15.6_update.xml"

$OSC api -X PUT '/source/test:release/_meta' --file "$FIXTURES_DIR/prj/test_release.xml"
$OSC api -X PUT '/source/home:Admin/_meta' --file "$FIXTURES_DIR/prj/home_Admin.xml"


# create package 'test:factory/test-pkgA'
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

$OSC checkout test:factory
cd "$_"

$OSC mkpac test-pkgA
cd "$_"

cp "$FIXTURES_DIR/pac/test-pkgA-1.spec" test-pkgA.spec
cp "$FIXTURES_DIR/pac/test-pkgA-1.changes" test-pkgA.changes
$OSC add test-pkgA.spec test-pkgA.changes
$OSC commit -m 'Initial commit'

cp "$FIXTURES_DIR/pac/test-pkgA-2.spec" test-pkgA.spec
cp "$FIXTURES_DIR/pac/test-pkgA-2.changes" test-pkgA.changes
$OSC commit -m 'Version 2'

cp "$FIXTURES_DIR/pac/test-pkgA-3.spec" test-pkgA.spec
cp "$FIXTURES_DIR/pac/test-pkgA-3.changes" test-pkgA.changes
$OSC commit -m 'Version 3'

rm -rf "$TMP_DIR"


# create package 'test:factory/test-pkgB'
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

$OSC checkout test:factory
cd "$_"

$OSC mkpac test-pkgB
cd "$_"

cp "$FIXTURES_DIR/pac/test-pkgB-1.spec" test-pkgB.spec
cp "$FIXTURES_DIR/pac/test-pkgB-1.changes" test-pkgB.changes
$OSC add test-pkgB.spec test-pkgB.changes
$OSC commit -m 'Initial commit'

cp "$FIXTURES_DIR/pac/test-pkgB-2.spec" test-pkgB.spec
cp "$FIXTURES_DIR/pac/test-pkgB-2.changes" test-pkgB.changes
$OSC commit -m 'Version 2'

rm -rf "$TMP_DIR"


# create package 'test:factory/multibuild-pkg'
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

$OSC checkout test:factory
cd "$_"

$OSC mkpac multibuild-pkg
cd "$_"

cp "$FIXTURES_DIR/pac/multibuild-pkg-1._multibuild" _multibuild
cp "$FIXTURES_DIR/pac/multibuild-pkg-1.spec" multibuild-pkg.spec
cp "$FIXTURES_DIR/pac/multibuild-pkg-1.changes" multibuild-pkg.changes

$OSC add _multibuild multibuild-pkg.spec multibuild-pkg.changes
$OSC commit -m 'Initial commit'

rm -rf "$TMP_DIR"


# create package 'test:leap:15.6/test-pkgA'
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

$OSC checkout test:leap:15.6
cd "$_"

$OSC mkpac test-pkgA
cd "$_"

cp "$FIXTURES_DIR/pac/test-pkgA-1.spec" test-pkgA.spec
cp "$FIXTURES_DIR/pac/test-pkgA-1.changes" test-pkgA.changes
$OSC add test-pkgA.spec test-pkgA.changes
$OSC commit -m 'Initial commit'

rm -rf "$TMP_DIR"


# create package 'test:devel/test-pkgA'
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

$OSC checkout test:devel
cd "$_"

$OSC mkpac test-pkgA
cd "$_"

# commit an empty package
$OSC commit -m 'Initial commit'

# set the devel project
$OSC setdevelproject test:factory/test-pkgA test:devel/test-pkgA
