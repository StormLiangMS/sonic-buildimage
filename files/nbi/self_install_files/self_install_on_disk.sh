#!/bin/bash -x
#
# Filename: self_install_on_disk.sh
# 

SELF_INSTALL_PATH="$(dirname "$(readlink -f "$0")")"

# source bash include files if provided by target NOS
if [ -e "$SELF_INSTALL_PATH/self_install_helper.include" ]; then
    source "$SELF_INSTALL_PATH/self_install_helper.include"
fi

# mount bootflash
nos_mount_bootflash
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

# install files in bootflash:
nos_install_image
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    nos_umount_bootflash
    exit $ret_val 
fi

# umount bootflash
nos_umount_bootflash
ret_val=$?
if [ $ret_val != $NOS_INSTALL_EXIT_SUCCESS ] ; then
    exit $ret_val 
fi

#update grub conf files
"$SELF_INSTALL_PATH"/nbi-sonic-autoboot.sh -i $(nos_run_image_path)
ret_val=$?
if [ $ret_val != 0 ] ; then
    exit $ret_val 
fi

exit $NOS_INSTALL_EXIT_SUCCESS

