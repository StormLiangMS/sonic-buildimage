#!/bin/bash -x
#
# Filename: nos_install_on_disk.sh
# 
# NX-OS installer would extract the NOS installer plugin files and
# invoke this script with the following 3 argumentsR to install
# the NOS in the bootflash: and update grub boot image info.
# 
# e.g., nos_install_on_disk.sh "/bootflash/sonic.iso"  \
#                              "/nxos/tmp/nos_plugin_extract_dir"  \
#                              "/nxos/tmp/"
#

# script arguments
NOS_IMAGE=$1
NOS_IPLUGIN_PATH=$2
SWITCH_GRUB_PATH=$3

# source bash include files if provided by target NOS
if [ -e $NOS_IPLUGIN_PATH/nos_install_helper.include ]; then
    source $NOS_IPLUGIN_PATH/nos_install_helper.include
fi

# install files in bootflash:
nos_install_image $NOS_IMAGE
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi


#update grub conf files
nos_update_grub_conf $NOS_IMAGE $SWITCH_GRUB_PATH
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

exit $NOS_INSTALL_EXIT_SUCCESS

