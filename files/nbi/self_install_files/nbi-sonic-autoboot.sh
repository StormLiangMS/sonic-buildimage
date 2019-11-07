#!/bin/bash

PROGNAME=${0##*/}

usage() {
    echo "Usage: $PROGNAME -r"
    echo "   or: $PROGNAME --revoke"
    echo "   or: $PROGNAME -i image_name"
    echo "   or: $PROGNAME --image image_name"
    exit 1
}

CFG0=/mnt/cfg/0/boot/grub/menu.lst.local
CFG0DIR=/mnt/cfg/0/boot/grub
CFG0MNT=/mnt/cfg/0
CFG0DEV=/dev/sda5
CFG1=/mnt/cfg/1/boot/grub/menu.lst.local
CFG1DIR=/mnt/cfg/1/boot/grub
CFG1MNT=/mnt/cfg/1
CFG1DEV=/dev/sda6

if [ $# == 0 ]; then
    usage
fi

OPTIONS=`getopt -o ri: --long revoke,image: -n "$PROGNAME" -- "$@"`

if [ $? != 0 ]; then
    usage
fi

eval set -- "$OPTIONS"

while :; do
    case $1 in
    -r|--revoke)
        revoke="yes"
        shift 1
        ;;
    -i|--image)
        image="$2"
        shift 2
        ;;
    --)
        shift
        break
        ;;
    *)
        echo "Unsupported option"
        usage
        ;;
    esac
done

# Make sure only root can run our script
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root" 1>&2
    exit 1
else
# Auto boot configuration file can be stored on partition /dev/sda5
    result=$(fdisk -l /dev/sda | grep -c "$CFG0DEV")
    if [[ $result -eq 0 ]]; then
        echo "Expect partition $CFG0DEV"
        exit 3
    fi
# Auto boot configuration file can be stored on partition /dev/sda6
    result=$(fdisk -l /dev/sda | grep -c "$CFG1DEV")
    if [[ $result -eq 0 ]]; then
        echo "Expect partition $CFG1DEV"
        exit 4
    fi
# Make directories and mount partitions
    mkdir -p "$CFG0MNT"
    mkdir -p "$CFG1MNT"
    mount "$CFG0DEV" "$CFG0MNT"
    mount "$CFG1DEV" "$CFG1MNT"

    if [ -n "${revoke+set}" ]; then
        rm -fr "$CFG0DIR"
        rm -fr "$CFG1DIR"
    fi

    if [ -n "${image+set}" ]; then
        mkdir -p "$CFG0DIR"
        chmod 777 "$CFG0DIR"
        mkdir -p "$CFG1DIR"
        chmod 777 "$CFG1DIR"

        touch $CFG0
        chmod 666 $CFG0
        cat << EOF > $CFG0 
#
# General configuration
#
disable certificate
# Menu entry for the available images
EOF
        echo title bootflash:/$image >> $CFG0
        echo boot bootflash:/$image >> $CFG0

        touch $CFG1
        chmod 666 $CFG1
        cat << EOF > $CFG1 
#
# General configuration
#
disable certificate
# Menu entry for the available images
EOF
        echo title bootflash:/$image >> $CFG1
        echo boot bootflash:/$image >> $CFG1

    fi

# Unmount partitions and remove directories 
    umount "$CFG0MNT"
    umount "$CFG1MNT"
    rmdir "$CFG0MNT"
    rmdir "$CFG1MNT"
    rmdir /mnt/cfg/
fi
