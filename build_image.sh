#!/bin/bash
## This script is to generate an ONIE installer image based on a file system overload

## Enable debug output for script
set -x -e

## Read ONIE image related config file

CONFIGURED_ARCH=$([ -f .arch ] && cat .arch || echo amd64)

if [[ $CONFIGURED_ARCH == armhf || $CONFIGURED_ARCH == arm64 ]]; then
    . ./onie-image-${CONFIGURED_ARCH}.conf
else
    . ./onie-image.conf
fi

[ -n "$ONIE_IMAGE_PART_SIZE" ] || {
    echo "Error: Invalid ONIE_IMAGE_PART_SIZE in onie image config file"
    exit 1
}
[ -n "$ONIE_INSTALLER_PAYLOAD" ] || {
    echo "Error: Invalid ONIE_INSTALLER_PAYLOAD in onie image config file"
    exit 1
}

IMAGE_VERSION=$(. functions.sh && sonic_get_version)
LINUX_KERNEL_VERSION=$(basename fsroot/boot/initrd.img-*-amd64 -amd64 | cut -b 12-)

generate_onie_installer_image()
{
    # Copy platform-specific ONIE installer config files where onie-mk-demo.sh expects them
    rm -rf ./installer/x86_64/platforms/
    mkdir -p ./installer/x86_64/platforms/
    for VENDOR in `ls ./device`; do
        for PLATFORM in `ls ./device/$VENDOR`; do
            if [ -f ./device/$VENDOR/$PLATFORM/installer.conf ]; then
                cp ./device/$VENDOR/$PLATFORM/installer.conf ./installer/x86_64/platforms/$PLATFORM
            fi

        done
    done

    ## Generate an ONIE installer image
    ## Note: Don't leave blank between lines. It is single line command.
    ./onie-mk-demo.sh $TARGET_PLATFORM $TARGET_MACHINE $TARGET_PLATFORM-$TARGET_MACHINE-$ONIEIMAGE_VERSION \
          installer platform/$TARGET_MACHINE/platform.conf $OUTPUT_ONIE_IMAGE OS $IMAGE_VERSION $ONIE_IMAGE_PART_SIZE \
          $ONIE_INSTALLER_PAYLOAD
}

if [ "$IMAGE_TYPE" = "onie" ]; then
    echo "Build ONIE installer"
    mkdir -p `dirname $OUTPUT_ONIE_IMAGE`
    sudo rm -f $OUTPUT_ONIE_IMAGE

    generate_onie_installer_image

## Build a raw partition dump image using the ONIE installer that can be
## used to dd' in-lieu of using the onie-nos-installer. Used while migrating
## into SONiC from other NOS.
elif [ "$IMAGE_TYPE" = "raw" ]; then

    echo "Build RAW image"
    mkdir -p `dirname $OUTPUT_RAW_IMAGE`
    sudo rm -f $OUTPUT_RAW_IMAGE

    generate_onie_installer_image

    echo "Creating SONiC raw partition : $OUTPUT_RAW_IMAGE of size $RAW_IMAGE_DISK_SIZE MB"
    fallocate -l "$RAW_IMAGE_DISK_SIZE"M $OUTPUT_RAW_IMAGE

    ## Generate a partition dump that can be used to 'dd' in-lieu of using the onie-nos-installer
    ## Run the installer 
    ## The 'build' install mode of the installer is used to generate this dump.
    sudo chmod a+x $OUTPUT_ONIE_IMAGE
    sudo ./$OUTPUT_ONIE_IMAGE

    [ -r $OUTPUT_RAW_IMAGE ] || {
        echo "Error : $OUTPUT_RAW_IMAGE not generated!"
        exit 1
    }

    gzip $OUTPUT_RAW_IMAGE

    [ -r $OUTPUT_RAW_IMAGE.gz ] || {
        echo "Error : gzip $OUTPUT_RAW_IMAGE failed!"
        exit 1
    }

    mv $OUTPUT_RAW_IMAGE.gz $OUTPUT_RAW_IMAGE
    echo "The compressed raw image is in $OUTPUT_RAW_IMAGE"

elif [ "$IMAGE_TYPE" = "kvm" ]; then

    echo "Build KVM image"
    KVM_IMAGE_DISK=${OUTPUT_KVM_IMAGE%.gz}
    sudo rm -f $KVM_IMAGE_DISK $KVM_IMAGE_DISK.gz

    generate_onie_installer_image

    SONIC_USERNAME=$USERNAME PASSWD=$PASSWORD sudo -E ./scripts/build_kvm_image.sh $KVM_IMAGE_DISK $onie_recovery_image $OUTPUT_ONIE_IMAGE $KVM_IMAGE_DISK_SIZE

    if [ $? -ne 0 ]; then
        echo "Error : build kvm image failed"
        exit 1
    fi

    [ -r $KVM_IMAGE_DISK ] || {
        echo "Error : $KVM_IMAGE_DISK not generated!"
        exit 1
    }

    gzip $KVM_IMAGE_DISK

    [ -r $KVM_IMAGE_DISK.gz ] || {
        echo "Error : gzip $KVM_IMAGE_DISK failed!"
        exit 1
    }

    echo "The compressed kvm image is in $KVM_IMAGE_DISK.gz"

## Use 'aboot' as target machine category which includes Aboot as bootloader
elif [ "$IMAGE_TYPE" = "aboot" ]; then
    echo "Build Aboot installer"
    mkdir -p `dirname $OUTPUT_ABOOT_IMAGE`
    sudo rm -f $OUTPUT_ABOOT_IMAGE
    sudo rm -f $ABOOT_BOOT_IMAGE
    ## Add main payload
    cp $ONIE_INSTALLER_PAYLOAD $OUTPUT_ABOOT_IMAGE
    ## Add Aboot boot0 file
    j2 -f env files/Aboot/boot0.j2 ./onie-image.conf > files/Aboot/boot0
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" files/Aboot/boot0
    pushd files/Aboot && zip -g $OLDPWD/$OUTPUT_ABOOT_IMAGE boot0; popd
    pushd files/Aboot && zip -g $OLDPWD/$ABOOT_BOOT_IMAGE boot0; popd
    echo "$IMAGE_VERSION" >> .imagehash
    zip -g $OUTPUT_ABOOT_IMAGE .imagehash
    zip -g $ABOOT_BOOT_IMAGE .imagehash
    rm .imagehash
    echo "SWI_VERSION=42.0.0" > version
    echo "SWI_MAX_HWEPOCH=2" >> version
    echo "SWI_VARIANT=US" >> version
    zip -g $OUTPUT_ABOOT_IMAGE version
    zip -g $ABOOT_BOOT_IMAGE version
    rm version

    zip -g $OUTPUT_ABOOT_IMAGE $ABOOT_BOOT_IMAGE
    rm $ABOOT_BOOT_IMAGE
elif [ "$IMAGE_TYPE" = "nbi" ]; then
    echo "Build NBI installer"
    mkdir -p `dirname $OUTPUT_NBI_IMAGE`
    sudo rm -f $OUTPUT_NBI_IMAGE
    sudo rm -f nbi-md5sums
    md5sum $FILESYSTEM_SQUASHFS $FILESYSTEM_DOCKERFS > nbi-md5sums
    sudo rm -f .imagehash
    echo "$IMAGE_VERSION" >> .imagehash
    sudo rm -f nos_install_plugin.tgz
    sudo rm -fr nos_plugin_files
    mkdir nos_plugin_files
    cp files/nbi/nos_plugin_files/* nos_plugin_files
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" nos_plugin_files/nos_install_helper.include
    #cp fsroot/sbin/kexec nos_plugin_files/nos_kexec
    cp files/nbi/nos_kexec nos_plugin_files/nos_kexec
    chmod +x nos_plugin_files/nos_kexec
    pushd nos_plugin_files && tar cvzf ../nos_install_plugin.tgz .; popd
    sudo rm -fr initrd-root
    mkdir initrd-root
    pushd initrd-root
    zcat ../fsroot/boot/initrd.img-${LINUX_KERNEL_VERSION}-amd64 | cpio -idmv
    if [ $? != 0 ]; then
        echo "Error:: Couldn\'t find ./fsroot/boot/initrd.img-${LINUX_KERNEL_VERSION}-amd64"
        exit 1
    fi
    cp ../nbi-md5sums nbi-md5sums
    cp ../.imagehash .imagehash
    mkdir -p isanboot/bin/images
    cp ../nos_install_plugin.tgz isanboot/bin/images/nos_install_plugin.tz
    [ "$(id -ru)" != 0 ] && cpio_owner_root="-R 0:0"
    find . | cpio --quiet $cpio_owner_root -o -H newc | gzip > ../nbi-run-initrd.img
    popd
    sudo rm -f $NBI_BOOT_IMAGE
    sudo rm -f files/nbi/mknbi-ks-ver.sh
    cp files/nbi/mknbi-ks.sh files/nbi/mknbi-ks-ver.sh
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" files/nbi/mknbi-ks-ver.sh
    pushd files/nbi && ./mknbi-ks-ver.sh ../../$NBI_BOOT_IMAGE sonic-run.seg4 ../../fsroot/boot/vmlinuz-${LINUX_KERNEL_VERSION}-amd64 ../../nbi-run-initrd.img; popd
    sudo rm nbi-run-initrd.img
    sudo rm -f files/nbi/mknbi-ks-ver.sh
    sudo rm -f nos_install_plugin.tgz
    sudo rm -fr nos_plugin_files
    mkdir nos_plugin_files
    cp files/nbi/nos_plugin_files/* nos_plugin_files
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" nos_plugin_files/nos_install_helper.include
    pushd nos_plugin_files && tar cvzf ../nos_install_plugin.tgz .; popd
    sudo rm -fr nbi-host
    mkdir -p nbi-host/image-$IMAGE_VERSION
    sudo rm -f nbi-"$ONIE_INSTALLER_PAYLOAD"
    pushd nbi-host/image-$IMAGE_VERSION && unzip ../../$ONIE_INSTALLER_PAYLOAD; popd
    cp .imagehash nbi-md5sums nbi-host/image-$IMAGE_VERSION
    cp $NBI_BOOT_IMAGE nbi-host/image-$IMAGE_VERSION
    cp files/nbi/x86_64-n9200-r0/machine.conf nbi-host/
    pushd nbi-host/ && zip -r ../nbi-"$ONIE_INSTALLER_PAYLOAD" .; popd
    sudo rm -fr initrd-root
    mkdir initrd-root
    pushd initrd-root
    zcat ../files/nbi/initrd.img | cpio -idmv
    cp ../nbi-"$ONIE_INSTALLER_PAYLOAD" nbi-"$ONIE_INSTALLER_PAYLOAD"
    mkdir -p isanboot/bin/images
    cp ../nos_install_plugin.tgz isanboot/bin/images/nos_install_plugin.tz
    cp ../.imagehash .
    rm etc/rcS.d/S17mount-flash
    rm etc/fstab
    cp ../files/nbi/fstab etc/fstab
    mkdir -p usr/local/install
    cp ../files/nbi/self_install_files/* usr/local/install/
    chmod +x usr/local/install/*
    mkdir -p sonic_installer_scripts
    cp ../fsroot/usr/local/bin/sonic-nbi-install.sh sonic_installer_scripts/
    chmod +x sonic_installer_scripts/*
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" usr/local/install/self_install_helper.include
    [ "$(id -ru)" != 0 ] && cpio_owner_root="-R 0:0"
    find . | cpio --quiet $cpio_owner_root -o -H newc | gzip > ../nbi-install-initrd.img
    popd
    sudo rm -fr initrd-root
    sudo rm -f nos_install_plugin.tgz
    sudo rm -fr nos_plugin_files
    sudo rm -f files/nbi/mknbi-bin-ver.sh
    cp files/nbi/mknbi-bin.sh files/nbi/mknbi-bin-ver.sh
    sed -i -e "s/%%IMAGE_VERSION%%/$IMAGE_VERSION/g" files/nbi/mknbi-bin-ver.sh
    pushd files/nbi && ./mknbi-bin-ver.sh ../../$OUTPUT_NBI_IMAGE sonic-install.seg4 ../../files/nbi/vmlinuz ../../nbi-install-initrd.img; popd
    sudo rm nbi-install-initrd.img
    sudo rm -f files/nbi/mknbi-bin-ver.sh
    sudo rm -fr nbi-host nbi-"$ONIE_INSTALLER_PAYLOAD" nbi-md5sums
else
    echo "Error: Non supported image type $IMAGE_TYPE"
    exit 1
fi
