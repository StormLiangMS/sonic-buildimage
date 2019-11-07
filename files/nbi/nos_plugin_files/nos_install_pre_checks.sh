#!/bin/bash -x
#
# Filename: nos_install_pre_checks.sh
# 
# NX-OS installer would extract the NOS installer plugin files and
# invoke this script with the following 2 arguments to perform
# pre-upg validations(md5, compatibility...)
# 
# e.g., nos_install_pre_checks.sh "bootflash/sonic.iso"  \
#                                 "/nxos/tmp/nos_plugin_extract_dir" 
#

# script arguments
NOS_IMAGE=$1
NOS_IPLUGIN_PATH=$2

# source bash include files if provided by target NOS
if [ -e $NOS_IPLUGIN_PATH/nos_install_helper.include ]; then
    source $NOS_IPLUGIN_PATH/nos_install_helper.include
fi

# MD5 check
nos_install_md5_check $NOS_IMAGE
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

# compatiblity check
nos_install_ver_check $NOS_IMAGE
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

exit $NOS_INSTALL_EXIT_SUCCESS

