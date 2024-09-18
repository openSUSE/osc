set -x
set -e


TOPDIR=$(dirname $(readlink -f "$0"))
source "$TOPDIR/common.sh"


# tweak configuration

# hard-code hostname to "localhost"
sed -i 's!^my $hostname = .*!my $hostname = "localhost";!' /usr/lib/obs/server/BSConfig.pm

# set signd server to "localhost" (workarounds the "will not proxy to myself" error)
sed -i 's!^#server: .*!server: localhost!' /etc/sign.conf

# limit number of workers
sed -i 's!^OBS_WORKER_INSTANCES=.*!OBS_WORKER_INSTANCES="1"!' /etc/sysconfig/obs-server

# enable xforward
sed -i 's!^#use_xforward:.*!use_xforward: true!' /srv/www/obs/api/config/options.yml

# configure passenger
sed -i -E 's!^(\s*)PassengerRuby .*!\1PassengerRuby "/usr/bin/ruby.ruby3.1"!' /etc/apache2/conf.d/mod_passenger.conf

# enable apache SSL server flag
sed -i 's!^APACHE_SERVER_FLAGS=.*!APACHE_SERVER_FLAGS="SSL"!' /etc/sysconfig/apache2

# also listen on the ports that are published outside the container
# so the included oscrc files are valid from both outside and inside of the container
sed -i 's!^<VirtualHost \*:82>!<VirtualHost *:82 *:1082>!' /etc/apache2/vhosts.d/obs.conf
sed -i 's!^<VirtualHost \*:443>!<VirtualHost *:443 *:1443>!' /etc/apache2/vhosts.d/obs.conf
sed -i 's!^Listen 82$!Listen 82\nListen 1082\nListen 1443!' /etc/apache2/vhosts.d/obs.conf


# enable apache mods
APACHE_MODS="passenger rewrite proxy proxy_http xforward headers ssl socache_shmcb"
for mod in $APACHE_MODS; do
  /usr/sbin/a2enmod $mod
done


# create missing dirs, set perms
mkdir -p /srv/obs/repos
chown obsrun:obsrun /srv/obs/repos
chmod 0755 /srv/obs/repos

mkdir -p /srv/obs/certs
chown root:root /srv/obs/certs
chmod 0700 /srv/obs/certs


# create a self-signed certificate for 'localhost'
cd /srv/obs/certs
openssl req -newkey rsa:4096 -x509 -sha256 -days 365 -nodes -addext "subjectAltName = DNS:localhost" -out server.crt -keyout server.key -subj '/CN=localhost'


# copy server cert into osc's trusted certs
mkdir -p /root/.config/osc/trusted-certs
cp /srv/obs/certs/server.crt /root/.config/osc/trusted-certs/localhost_443.pem


# configure mysql
cat <<EOF > /etc/my.cnf.d/obs-server.cnf
[mysqld]
bind-address = 127.0.0.1
datadir = /srv/obs/MySQL

[mysqld_multi]
datadir = /srv/obs/MySQL
EOF


# mysql user's home
mkdir -p /var/lib/mysql
chown mysql:mysql /var/lib/mysql
chmod 0700 /var/lib/mysql

# datadir for OBS
mkdir -p /srv/obs/MySQL
chown mysql:mysql /srv/obs/MySQL
chmod 0700 /srv/obs/MySQL


# initialize database
init_mysql
start_mysql
sleep 1


# set mysql superuser's password; user=root, password=opensuse
mysqladmin -u root password opensuse
echo "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('opensuse');" | mysql


# start srcserver (needed for OBS initialization)
start_obs_srcserver


# initialize the OBS database
cd /srv/www/obs/api
RAILS_ENV=production SAFETY_ASSURED=1 bin/rails db:setup writeconfiguration


# update configuration and write it to disk
echo "update configurations set admin_email='admin@example.com';" | su -s /bin/sh - mysql -c "mysql api_production"
echo "update configurations set download_url='http://localhost:1082';" | su -s /bin/sh - mysql -c "mysql api_production"
echo "update configurations set obs_url='https://localhost:1443';" | su -s /bin/sh - mysql -c "mysql api_production"
cd /srv/www/obs/api; RAILS_ENV=production SAFETY_ASSURED=1 bin/rails writeconfiguration


# fix perms
chown -R wwwrun:www /srv/www/obs/api/log/
chown -R wwwrun:www /srv/www/obs/api/tmp/


# OBS api
#systemctl enable memcached
systemctl enable apache2
systemctl enable mysql
# starting obs-api-support.target incl. all dependencies is expensive
# let's mask it and start individual services as needed
systemctl mask obs-api-support.target

# OBS backend
systemctl enable obssrcserver
systemctl enable obsrepserver
#systemctl enable obsdispatcher
#systemctl enable obspublisher
#systemctl enable obsscheduler
systemctl enable obsservice
#systemctl enable obssignd
#systemctl enable obssigner
#systemctl enable obswarden
#systemctl enable obsdodup
#systemctl enable obsdeltastore
#systemctl enable obsservicedispatch

# decouple obs-* services from obs-api-support.target
sed -i '/^BindsTo *=.*/d; s/^WantedBy *=.*/WantedBy = default.target/' /usr/lib/systemd/system/obs-*

# needed (not only) for generating diffs in requests
# systemctl enable obs-delayedjob-queue-default

# OBS worker
# systemctl enable obsworker
