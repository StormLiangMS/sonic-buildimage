#!/usr/bin/env bash

ROLE=$(sonic-cfggen -d -v "DEVICE_METADATA['localhost']['type']")

# Only start the directed broadcast forwarding daemon if our role is ToR
if [ $ROLE == "ToRRouter" ]; then
    exec /usr/bin/directed_bcastd
fi

exit 0
