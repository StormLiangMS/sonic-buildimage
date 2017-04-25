#!/bin/bash -e

rm -f /var/run/rsyslogd.pid
service rsyslog start     

## Test if joined to a domain
#AD_JOINED=0
#/opt/quest/bin/vastool info domain || AD_JOINED=$?
#
#if [ "$AD_JOINED" -ne "0" ]; then
#    if [ "$AD_JOINED" -ne "10" ]; then
#        echo "vastool info domain returns error code $AD_JOINED"
#        exit 1
#    fi
#
#    # Join correct domain if not already joined
#    sonic-cfggen -y /etc/sonic/ad.yml -t /usr/share/sonic/templates/join_domain.sh.j2 >/usr/sbin/join_domain.sh
#    chmod +x /usr/sbin/join_domain.sh
#    /usr/sbin/join_domain.sh
#fi

# Generate config files
mkdir -p /etc/opt/quest/vas
sonic-cfggen -m /etc/sonic/minigraph.xml -y /etc/sonic/ad.yml -t /usr/share/sonic/templates/users.allow.j2 >/etc/opt/quest/vas/users.allow
                                                                                              
# Set up sudoers
sonic-cfggen -m /etc/sonic/minigraph.xml -y /etc/sonic/ad.yml -t /usr/share/sonic/templates/sudoers.j2 >/etc/sudoers.tmp
visudo -q -c -f /etc/sudoers.tmp 
cp -f /etc/sudoers.tmp /etc/sudoers
cp -f /etc/sudoers.tmp /host/etc/sudoers

# Enable AD / sudo integration
/opt/quest/bin/vastool configure sudo

# Copy pam .so to host
mkdir -p /host/lib/x86_64-linux-gnu/security
cp --remove-destination /opt/quest/lib64/nss/libnss_vas4.so.2  \
                        /host/lib/x86_64-linux-gnu/
cp --remove-destination /opt/quest/lib64/security/pam_vas3.so  \
                        /host/lib/x86_64-linux-gnu/security/
cp --remove-destination /etc/nsswitch.conf                     \
                        /host/etc/

service vasd start

# Make sure entry point does not exit
read
