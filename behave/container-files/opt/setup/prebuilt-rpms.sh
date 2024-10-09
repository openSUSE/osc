set -x
set -e


TOPDIR=$(dirname $(readlink -f "$0"))
source "$TOPDIR/common.sh"


start_obs_srcserver
start_obs_repserver
sleep 1


FIXTURES_DIR="$TOPDIR/fixtures"


function upload_rpms() {
    local TMP_DIR=$(mktemp -d)
    local RPM_DIR="$1"
    local PROJECT="$2"
    local REPO="$3"
    local ARCH="$4"
    local PACKAGE="$5"

    # scan directory for all RPMs and link them to a flat dir to avoid
    # 400 remote error: cpio filename contains a '/'
    find "$RPM_DIR/SRPMS" -name '*.rpm' -exec ln -s {} "$TMP_DIR/" \; || :
    find "$RPM_DIR/RPMS/noarch" -name '*.rpm' -exec ln -s {} "$TMP_DIR/" \; || :
    find "$RPM_DIR/RPMS/$ARCH" -name '*.rpm' -exec ln -s {} "$TMP_DIR/" \; || :
    pushd "$TMP_DIR"
    find -name '*.rpm' | cpio --create --dereference -H newc > upload.cpio
    curl \
        --data-binary '@upload.cpio' \
        -H 'X-username: Admin' \
        -H 'Content-Type: application/x-cpio' \
        "http://localhost:5352/build/$PROJECT/$REPO/$ARCH/$PACKAGE"
    rm -rf "$TMP_DIR"
    popd
}


# build package 'test:factory/test-pkgA'
TMP_DIR=$(mktemp -d)
rpmbuild -ba "$FIXTURES_DIR/pac/test-pkgA-3.spec" --define "_topdir $TMP_DIR"
upload_rpms "$TMP_DIR" test:factory standard i586 test-pkgA
upload_rpms "$TMP_DIR" test:factory standard x86_64 test-pkgA
rm -rf "$TMP_DIR"


# build package 'test:factory/test-pkgB'
TMP_DIR=$(mktemp -d)
setarch i586 rpmbuild -ba "$FIXTURES_DIR/pac/test-pkgB-2.spec" --define "_topdir $TMP_DIR"
upload_rpms "$TMP_DIR" test:factory standard i586 test-pkgB
rm -rf "$TMP_DIR"

TMP_DIR=$(mktemp -d)
rpmbuild -ba "$FIXTURES_DIR/pac/test-pkgB-2.spec" --define "_topdir $TMP_DIR"
upload_rpms "$TMP_DIR" test:factory standard x86_64 test-pkgB
rm -rf "$TMP_DIR"


# build package 'test:factory/multibuild-pkg'
TMP_DIR=$(mktemp -d)
rpmbuild -ba "$FIXTURES_DIR/pac/multibuild-pkg-1.spec" --define "_topdir $TMP_DIR" --target=x86_64,i586 --define "flavor %{nil}"
upload_rpms "$TMP_DIR" test:factory standard i586 multibuild-pkg
upload_rpms "$TMP_DIR" test:factory standard x86_64 multibuild-pkg
rm -rf "$TMP_DIR"


# build package 'test:factory/multibuild-pkg:flavor1'
TMP_DIR=$(mktemp -d)
rpmbuild -ba "$FIXTURES_DIR/pac/multibuild-pkg-1.spec" --define "_topdir $TMP_DIR" --target=x86_64,i586 --define "flavor flavor1"
upload_rpms "$TMP_DIR" test:factory standard i586 multibuild-pkg:flavor1
upload_rpms "$TMP_DIR" test:factory standard x86_64 multibuild-pkg:flavor1
rm -rf "$TMP_DIR"


# build package 'test:factory/multibuild-pkg:flavor2'
TMP_DIR=$(mktemp -d)
rpmbuild -ba "$FIXTURES_DIR/pac/multibuild-pkg-1.spec" --define "_topdir $TMP_DIR" --target=x86_64,i586 --define "flavor flavor2"
upload_rpms "$TMP_DIR" test:factory standard i586 multibuild-pkg:flavor2
upload_rpms "$TMP_DIR" test:factory standard x86_64 multibuild-pkg:flavor2
rm -rf "$TMP_DIR"


# run scheduler to process all jobs
/usr/lib/obs/server/bs_sched --testmode i586
/usr/lib/obs/server/bs_sched --testmode x86_64


# run publisher
# noarch packages from x86_64 win over those from i586
/usr/lib/obs/server/bs_publish --testmode


# create fake empty files that usually accompany RPMs
ARCHES="i586 x86_64"
PACKAGES="test-pkgA test-pkgB multibuild-pkg multibuild-pkg:flavor1 multibuild-pkg:flavor2"
FILES="_buildenv _statistics rpmlint.log"
for ARCH in $ARCHES; do
    for PACKAGE in $PACKAGES; do
        for FILE in $FILES; do
            runuser -l obsrun -s /bin/bash -c "touch /srv/obs/build/test:factory/standard/$ARCH/$PACKAGE/$FILE"
        done
    done
done
