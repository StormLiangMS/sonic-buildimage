#! /bin/bash
output_file="$1"
vendor_file="$2"
kernel_file="$3"
initrd_file="$4"
./mknbi-insieme --rootdir=/dev/ram0 --rdbase=0x8000000 --append="BOOT_IMAGE=/bzImage acpi_enforce_resources=lax efi_no_storage_paranoia" --output="$output_file" --target=linux --format=nbi --vendorinfo="$vendor_file" "$kernel_file" "$initrd_file"
