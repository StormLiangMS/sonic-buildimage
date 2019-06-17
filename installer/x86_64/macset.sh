#!/bin/sh

#mac_bytes represents the number of bytes to be written
mac_bytes=6

#ethernet contoller magic
eth_dev_magic=0x04388086
eth_dev=eth0

mac_addr=$(cat /sys/class/net/$eth_dev/address)
mac_read=$(ethtool -e $eth_dev | grep 0x0000 | awk -v OFS=: '{print $2,$3,$4,$5,$6,$7}')
if [ "$mac_addr" != "$mac_read" ]
then
    for i in `seq 1 $mac_bytes`
    do
        var=$(echo "$mac_addr" | cut  -d':' -f$i)
        offset=$(($i-1))
        ethtool -E $eth_dev magic $eth_dev_magic offset 0x$(printf %x ${offset}) value 0x$var
    done
    #re-check mac value after setting
    mac_read=$(ethtool -e $eth_dev | grep 0x0000 | awk -v OFS=: '{print $2,$3,$4,$5,$6,$7}')
    if [ "$?" = "0" ]
    then
        echo -e "\nProgrammed mac for $eth_dev to $mac_read"
    else
        echo "Ethtool Error: could not set the mac address" >&2
        exit 1
    fi
else
    echo -e "\nMac for $eth_dev is already correctly configured to $mac_read"
fi