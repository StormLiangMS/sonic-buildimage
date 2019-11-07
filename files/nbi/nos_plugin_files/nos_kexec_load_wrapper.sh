#!/bin/bash -x
#
# Filename: nos_kexec_load_wrapper.sh
# 
# NX-OS installer would invoke this wrapper script
# to load the NOS image for kexec reboot
# 
# e.g., nos_kexec_load_wrapper.sh "/bootflash/sonic.iso"  \
#                                 "/nxos/tmp/nos_plugin_extract_dir" 
#

# script arguments
NOS_IMAGE=$1
NOS_IPLUGIN_PATH=$2

# source bash include files if provided by target NOS
if [ -e $NOS_IPLUGIN_PATH/nos_install_helper.include ]; then
    source $NOS_IPLUGIN_PATH/nos_install_helper.include
fi

# load NOS kernel and initrd images
nos_install_kexec_load $NOS_IMAGE
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

exit $NOS_INSTALL_EXIT_SUCCESS

