#!/bin/bash
#
# Description:
#     A bash script which partitions the disk into nxos layout
#
# The internal flash (/dev/sdX) layout is as follows:
#
# N3K platforms
# /dev/sdX1 (/dev/hd-bootloader): 8MB, mounted on $MNT_BOOTLOADER_DIR
# /dev/sdX3 (/dev/hd-bootflash): the rest, mounted on $MNT_BOOTFLASH
# /dev/sdX4 (/dev/hd-pss): 80MB, mounted on $MNT_PSS_DIR
# /dev/sdX5 (/dev/hd-cfg0): 80MB, mounted on $MNT_CFG0_DIR
# /dev/sdX6 (/dev/hd-cfg1): 80MB, mounted on $MNT_CFG1_DIR
#
# N9K platforms
# /dev/sdX1 (/dev/hd-bootloader): 8MB, mounted on $MNT_BOOTLOADER_DIR
# /dev/sdX2 (/dev/hd-plog): 32M, mounted on $MNT_PLOG_DIR
# /dev/sdX3 (/dev/hd-pss): 128M, mounted on $MNT_PSS_DIR
# /dev/sdX4 (/dev/hd-bootflash): the rest, mounted on $MNT_BOOTFLASH
# /dev/sdX5 (/dev/hd-cfg0): 64MB, mounted on $MNT_CFG0_DIR
# /dev/sdX6 (/dev/hd-cfg1): 64MB, mounted on $MNT_CFG1_DIR
# /dev/sdX7 (/dev//dev/hd-logflash): 4G/8G/16G , mounted on $MNT_LOGFLASH_DIR
#

SELF_INSTALL_PATH="$(dirname "$(readlink -f "$0")")"

# source bash include files if provided by target NOS
if [ -e "$SELF_INSTALL_PATH/self_install_helper.include" ]; then
    source "$SELF_INSTALL_PATH/self_install_helper.include"
fi

#trap ctrl-c and call ctrl_c()
trap ctrl_c INT

function ctrl_c()
{
    exit 1
}

PLATFORM_TYPE=$(nos_get_platform_type)
if [ $? -ne 0 ]; then
    echo "Platform not supported"
    exit 1
fi
PHYDEV=$(get_bootflash_disk_device)
if [ $? -ne 0 ]; then
    echo "Bootflash disk not found"
    exit 1
fi
BOOTDEV="$PHYDEV"1
FDISK=fdisk
GDISK=gdisk
MKFS="mke2fs -c -I 128"


DEVSDA1="$PHYDEV"1
DEVSDA2="$PHYDEV"2
DEVSDA3="$PHYDEV"3
DEVSDA4="$PHYDEV"4
DEVSDA5="$PHYDEV"5
DEVSDA6="$PHYDEV"6
DEVSDA7="$PHYDEV"7

#Common files
DEV_BOOTLOADER_FILE=$DEVSDA1
DEV_CFG0_FILE=$DEVSDA5
DEV_CFG1_FILE=$DEVSDA6

#N3K files
DEV_BOOTFLASH_N3K_FILE=$DEVSDA3
DEV_PSS_N3K_FILE=$DEVSDA4

#N9K files
DEV_BOOTFLASH_N9K_FILE=$DEVSDA4
DEV_PSS_N9K_FILE=$DEVSDA3
DEV_PLOG_N9K_FILE=$DEVSDA2
DEV_LOGFLASH_N9K_FILE=$DEVSDA7

MNT_CFG0_DIR=/mnt/cfg/0
MNT_CFG1_DIR=/mnt/cfg/1
MNT_BOOTFLASH_DIR=/bootflash

function doumountfs {
    if [ -n "`mount | grep $1`" ]; then
        umount $1
        if [ $? -ne 0 ]; then
            echo "Cannot umount filesystem"
            exit 1;
        fi
    fi
}

# function to unmount for N3K platforms
function umountfs_N3K {
    for i in `seq 1 6`;
    do
        doumountfs "$PHYDEV"$i
    done
}

# function to unmount for N9K platforms
function umountfs_N9K {
    for i in `seq 1 7`;
    do
        doumountfs "$PHYDEV"$i
    done
}

function domountfs {
    if [ ! -d $1 ]; then
        mkdir -p $1
    fi
    mount $2 $1
    if [ $? -ne 0 ]; then
        echo "ERROR: cannot mount filesystem"
    fi
}

# function to mount for N3K platforms
function mountfs_N3K {
    domountfs $MNT_BOOTFLASH_DIR $DEV_BOOTFLASH_N3K_FILE
    domountfs $MNT_CFG0_DIR $DEVSDA5
    domountfs $MNT_CFG1_DIR $DEVSDA6
    chmod 777 $MNT_BOOTFLASH_DIR
}

# function to mount for N9K platforms
function mountfs_N9K {
    domountfs $MNT_BOOTFLASH_DIR $DEV_BOOTFLASH_N9K_FILE
    domountfs $MNT_CFG0_DIR $DEV_CFG0_FILE
    domountfs $MNT_CFG1_DIR $DEV_CFG1_FILE
    chmod 777 $MNT_BOOTFLASH_DIR
}

function mkpartitions_N3K {

    # delete all current partitions

    CREATECMD="d\n1\nd\n2\nd\n3\nd\n4\nn\np\n1\n\n+8M\nn\ne\n2\n\n+80M\nn\np\n4\n\n+40M\nn\np\n3\n\n\nn\n\n+40M\nn\n\n\nw\n"

    echo -e $CREATECMD | $FDISK $PHYDEV >/dev/null 2>&1

    if [ $? -ne 0 ]; then
        echo "Partitioning failed"
        exit 1
    fi
}

function mkpartitions_N9K {

    local TOTAL_KB

    local BOOT_PART_SIZE
    local BOOTFLASH_PART_SIZE

    local DELETE_PARTS
    local CREATE_BOOT_PART
    local CREATE_BOOTFLASH_PART
    local CREATE_LOGFLASH_PART
    local CREATE_CFG0_PART
    local CREATE_CFG1_PART
    local CREATE_PSS_PART
    local CREATE_PLOG_PART
    local WRITE_PARTS
    local GDISK_CMDS


    local NR_OTHER_PARTS=4

    # Partitioning scheme
    #
    # part1 - bootloader    - 512M       - sda1
    # part2 - plog          - 32M        - sda2
    # part3 - pss           - 128M       - sda3
    # part4 - bootflash     - Rem        - sda4
    # part5 - cfg0          - 64M        - sda5
    # part6 - cfg1          - 64M        - sda6
    # part7 - logflash      - 4G/8G/16G  - sda7
    # logflash is 16G for SSD size > 64G.
    #              4G for 16GB eUSB

    TOTAL_KB=$(($(cat /sys/block/$(basename $PHYDEV)/size)*512/1024))
    #Leave some space for alignment.
    TOTAL_KB=$(($TOTAL_KB - 16*1024))

    # in KBs
    ONE_MB=$((1024))
    HALF_GB=$((512*1024))
    ONE_GB=$((1024*1024))


    # 512 MB
    BOOT_PART_SIZE=$HALF_GB
    # Rest all 64MB
    PLOG_PART_SIZE=$(($ONE_MB*32))
    PSS_PART_SIZE=$(($ONE_MB*128))
    CFG0_PART_SIZE=$(($ONE_MB*64))
    CFG1_PART_SIZE=$(($ONE_MB*64))
    SUM_ABOVE=$(($BOOT_PART_SIZE + $PLOG_PART_SIZE + $PSS_PART_SIZE + $CFG0_PART_SIZE + $CFG1_PART_SIZE))

    # 8G/16G
    LOGFLASH_PART_SIZE=$((4*$ONE_GB))
    if [ $TOTAL_KB -gt $((16*$ONE_GB)) ]; then
        LOGFLASH_PART_SIZE=$((8*$ONE_GB))
    elif [ $TOTAL_KB -gt $((64*$ONE_GB)) ]; then
        LOGFLASH_PART_SIZE=$((16*$ONE_GB))
    fi

    # Rem
    BOOTFLASH_PART_SIZE=$(($TOTAL_KB - $SUM_ABOVE - $LOGFLASH_PART_SIZE))

    if [ $BOOTFLASH_PART_SIZE -le 0 ]; then
        echo "Partitioning failed due to unavailable space."
        exit 1
    fi

    DELETE_PARTS="2\no\nY\n"
    CREATE_BOOT_PART="n\n\n\n+"$BOOT_PART_SIZE"KB\nEF00\n"
    CREATE_PLOG_PART="n\n\n\n+"$PLOG_PART_SIZE"KB\n\n"
    CREATE_BOOTFLASH_PART="n\n\n\n+"$BOOTFLASH_PART_SIZE"KB\n\n"
    CREATE_CFG0_PART="n\n\n\n+"$CFG0_PART_SIZE"KB\n\n"
    CREATE_CFG1_PART="n\n\n\n+"$CFG1_PART_SIZE"KB\n\n"
    CREATE_PSS_PART="n\n\n\n+"$PSS_PART_SIZE"KB\n\n"
    CREATE_LOGFLASH_PART="n\n\n\n+"$LOGFLASH_PART_SIZE"KB\n\n"
    WRITE_PARTS="\nw\nY\n"

    # Wipe all
    GDISK_CMDS=""$DELETE_PARTS""
    #/dev/sda1
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_BOOT_PART""
    #/dev/sda2
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_PLOG_PART""
    #/dev/sda3
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_PSS_PART""
    #/dev/sda4
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_BOOTFLASH_PART""
    #/dev/sda5
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_CFG0_PART""
    #/dev/sda6
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_CFG1_PART""
    #/dev/sda7
    GDISK_CMDS=""$GDISK_CMDS""$CREATE_LOGFLASH_PART""
    # Commit the changes
    GDISK_CMDS=""$GDISK_CMDS""$WRITE_PARTS""

    str=`echo -ne "$GDISK_CMDS" | ${GDISK} /dev/$(basename $PHYDEV)`
    #gdisk returns 1 on success. Look for success string in the output
    #clip the output ".*The operation has completed"
    ret=`echo ${str#*The operation has completed}`

    if [ "$ret" != "successfully." ]; then
        echo "Partitioning failed"
        exit 1
    fi
}

function mkfilesystem {

    $MKFS $@ >/dev/null 2>&1

    if [ $? -ne 0 ]; then
        echo "failed"
        exit 1
    fi
}


#check to see if the description file is available for "$PHYDEV"- if not then
#abort since there is some issue with the flash
EXISTS=$( grep $( echo $PHYDEV | sed -e 's/\/dev\///' ) "/proc/partitions" 2>/dev/null 2>&1)
if [ -z "$EXISTS" ]; then
    echo "There is a problem with the compact flash. It could not be initialized."
    exit 1
fi

if [ $PLATFORM_TYPE == "N3k" ]; then
    #N3k platforms
    ${FDISK} -l $PHYDEV

    echo
    echo "If you continue, you will delete above partitions/file systems"
    echo "and will create new NxOS partitions/file systems."
    read -p "Continue (y/n) ? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit
    fi

    echo "Please be patient."
    echo "It will take couple of minutes to create new file systems"
    # create the device files if needed
    if [ ! -b "$PHYDEV" ]; then
        mknod "$PHYDEV" b 8 16
        mknod "$PHYDEV"1 b 8 17
        mknod "$PHYDEV"2 b 8 18
        mknod "$PHYDEV"3 b 8 19
        mknod "$PHYDEV"4 b 8 20
        mknod "$PHYDEV"5 b 8 21
        mknod "$PHYDEV"6 b 8 22
    fi

    umountfs_N3K

    dd if=/dev/zero of=$PHYDEV bs=512 count=1 >/dev/null 2>&1
    parted -s $PHYDEV mklabel msdos >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "mklabel msdos failed"
        exit 1
    fi

    mkpartitions_N3K

    # Below sleep is required because at end of fdisk it mounts "$PHYDEV"*
    # to /media/sda*. This happens with little delay after fdisk finishes and
    # hence causes mk2efs to fail, since devices were mounted.
    sleep 5
    umountfs_N3K

    mkfilesystem $DEV_BOOTLOADER_FILE

    mkfilesystem -j $DEV_CFG0_FILE
    mkfilesystem -j $DEV_CFG1_FILE

    mkfilesystem -j $DEV_PSS_N3K_FILE

    #echo "Formatting bootflash:"
    mkfilesystem -j $DEV_BOOTFLASH_N3K_FILE

    echo "Done."

    exit
fi

if [ $PLATFORM_TYPE == "N9k" ]; then
    #For N9K platforms
    ${GDISK} -l /dev/$(basename $PHYDEV)

    echo
    echo "If you continue, you will delete above partitions/file systems"
    echo "and will create new NxOS partitions/file systems."
    read -p "Continue (y/n) ? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit
    fi

    echo "Please be patient."
    echo "It will take couple of minutes to create new file systems"

    umountfs_N9K

    mkpartitions_N9K

    partprobe

    mkfilesystem $DEV_BOOTLOADER_FILE
    mkfilesystem -j $DEV_CFG0_FILE
    mkfilesystem -j $DEV_CFG1_FILE
    mkfilesystem -j $DEV_PSS_N9K_FILE
    mkfilesystem -j $DEV_PLOG_N9K_FILE
    mkfilesystem -j $DEV_BOOTFLASH_N9K_FILE
    mkfilesystem -j $DEV_LOGFLASH_N9K_FILE

    echo "Done."

    exit
fi
