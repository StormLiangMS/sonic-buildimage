#!/bin/bash

HWSKU=$(sonic-cfggen -d -v 'DEVICE_METADATA["localhost"]["hwsku"]')
if [[ "$HWSKU" != "Arista-7260CX3-C64" ]]; then
   logger "Skipping Lossless Buffer Profile Mitigation for HWSKU:"$HWSKU
   exit 0
fi
ACTIVE_PORT_LIST=($(sonic-cfggen -d -v 'DEVICE_NEIGHBOR|list' | tr -d '[],'))
for PORT in "${ACTIVE_PORT_LIST[@]}"
do
    PORTNAME=$(echo $PORT | sed -e 's/'u/'/')
    PORT_SPEED=$(sonic-cfggen -d -v 'PORT['$PORTNAME']["speed"]')
    if [[ "$PORT_SPEED" -eq "40000" ]]; then
        ACTIVE_40G_PORT_LIST+=("$PORTNAME")
    fi
done

ACTIVE_40G_PORT_LIST_COUNT=${#ACTIVE_40G_PORT_LIST[@]}

if [[ "$ACTIVE_40G_PORT_LIST_COUNT" -eq "0" ]]; then
    logger "Skipping Mitigation for for HWSKU:"$HWSKU" as no active 40G port"
    exit 0
fi
echo "Wait for 30 sec before binding Lossless profile to TC"
sleep 30
for PORT in "${ACTIVE_40G_PORT_LIST[@]}"
do
    redis-cli -n 4 hset "BUFFER_PG|"$(eval echo $PORT)"|3-4" "profile" "[BUFFER_PROFILE|pg_lossless_40000_300m_profile]" > /dev/null
    logger "Applying Lossless Buffer Profile Mitigation for HWSKU:"$HWSKU" Port:"$PORT
done
sudo config save -y
logger "Lossless Mitigation Applied for HWSKU:"$HWSKU" and config saved !!"
echo "Lossless Mitigation Applied for HWSKU:"$HWSKU" and config saved !!"
exit 0
