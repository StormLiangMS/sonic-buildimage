#!/usr/bin/env bash

rm -f /var/run/rsyslogd.pid
supervisorctl start rsyslogd

mkdir -p /var/opt/msft/client
cp /acms/acms_secrets.ini /var/opt/msft/client/

mkdir -p /var/opt/msft/acms
cp /acms/acms.ini /var/opt/msft/acms

BOOTSTRAP_CERT="/etc/sonic/credentials/"
SONIC_CREDS_PATH="/etc/sonic/credentials/"
SONIC_ACMS_BOOTSTRAP_PATTERN="sonic_acms_bootstrap-.*\.pfx"
DSMS_CONF="/var/opt/msft/client/dsms.conf"

supervisorctl start dSMS_config_modifier
sleep 5

# Wait for ACMS config to be updated
while true
do
    text=`supervisorctl status dSMS_config_modifier`
    if [[ $text == *"EXITED"* ]]; then
        break
    fi
    sleep 5
done

# Determine the bootstrap cert file name
text=`ls $SONIC_CREDS_PATH | grep $SONIC_ACMS_BOOTSTRAP_PATTERN`
num_files=`echo $text | wc -l`
if [ $num_files -eq 1 ]; then
    BOOTSTRAP_CERT=$BOOTSTRAP_CERT$text
    logger "BOOTSTRAP_CERT=$BOOTSTRAP_CERT"
else
    logger "More than one bootstrap cert file found!"
    exit 1
fi

check_bootstrap_status() {
    logger "Checking for bootstrap status"
    if [ -f $DSMS_CONF ]; then
        while IFS= read -r line; do
            if [[ $line == *"HasBootstrapped=yes"* ]]; then
                logger "ACMS is already bootstrapped"
                return 1
            fi
        done < $DSMS_CONF
    fi
    return 0
}

check_bootstrap_status
BOOTSTRAP_STATUS=$?

while [[ $BOOTSTRAP_STATUS = 0 ]]
do
    if [[ -f $BOOTSTRAP_CERT ]]; then
        # Bootstrap ACMS
        /usr/bin/acms -Bootstrap -Dependant client -BaseDirPath /var/opt/msft/
        check_bootstrap_status
        BOOTSTRAP_STATUS=$? 
        # Retry if bootstrap fails
        if [[ $BOOTSTRAP_STATUS = 0 ]]; then
            rm /var/opt/msft/client/dsms.conf
        fi
    else
        logger "Waiting for bootstrap cert"
    fi
    sleep 60
done
logger "ACMS bootstrapping complete"

# Start ACMS
logger "Starting ACMS"
supervisorctl start acms
