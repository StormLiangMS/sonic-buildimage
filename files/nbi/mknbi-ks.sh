#! /bin/bash
output_file="$1"
vendor_file="$2"
kernel_file="$3"
initrd_file="$4"
./mknbi-insieme --rootdir=/dev/sda4 --rdbase=0x8000000 --append="quiet noefi net.ifnames=0 biosdevname=0 loop=image-%%IMAGE_VERSION%%/fs.squashfs loopfstype=squashfs apparmor=1 security=apparmor varlog_size=4096" --output="$output_file" --target=linux --format=nbi --vendorinfo="$vendor_file" "$kernel_file" "$initrd_file"
