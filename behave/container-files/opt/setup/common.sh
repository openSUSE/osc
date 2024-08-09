set -x
set -e


MYSQL_HELPER=/usr/libexec/mysql/mysql-systemd-helper
if [ ! -f "$MYSQL_HELPER" ]; then
    MYSQL_HELPER=/usr/lib/mysql/mysql-systemd-helper
fi


function init_mysql {
    "$MYSQL_HELPER" install
    "$MYSQL_HELPER" upgrade
}


function start_mysql {
    su --shell=/bin/bash - mysql "$MYSQL_HELPER" start 2>&1 >/dev/null &
}


function start_apache {
    /usr/sbin/start_apache2 -DSYSTEMD -DFOREGROUND -k start &
}


function start_obs_repserver {
    /usr/lib/obs/server/bs_repserver --logfile rep_server.log 2>&1 >/dev/null &
}


function start_obs_srcserver {
    /usr/lib/obs/server/bs_srcserver --logfile src_server.log 2>&1 >/dev/null &
}


function start_obs_scheduler {
    /usr/sbin/obsscheduler start
}
