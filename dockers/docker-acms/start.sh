#!/usr/bin/env bash

rm -f /var/run/rsyslogd.pid

supervisorctl start rsyslogd
supervisorctl start cert_converter

mkdir -p /var/opt/msft/client
cp /acms/acms_secrets.ini /var/opt/msft/client/

mkdir -p /var/opt/msft/acms
cp /acms/acms.ini /var/opt/msft/acms


BOOTSTRAP_CERT=/acms/bootstrap.pfx
DSMS_CONF=/var/opt/msft/client/dsms.conf

BOOTSTRAP_STATUS=0
if [ -f $DSMS_CONF ]; then
    while IFS= read -r line; do
        if [[ $line == *"HasBootstrapped=yes"* ]]; then
            BOOTSTRAP_STATUS=1
            break
        fi
    done < $DSMS_CONF
fi

while [ : ]
do
    if [[ -f $BOOTSTRAP_CERT && $BOOTSTRAP_STATUS = 0 ]]; then
        # Bootstrap ACMS
        /usr/bin/acms -Bootstrap -Dependant client -BaseDirPath /var/opt/msft/
        break
    fi
    sleep 5s
done

# Start ACMS
/usr/bin/acms -Start -BaseDirPath /var/opt/msft/