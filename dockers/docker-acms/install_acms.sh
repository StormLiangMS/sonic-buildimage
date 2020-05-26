#!/usr/bin/env bash

# Update the public key to download ACMS client
apt-key add /acms/msftPackagesKey.pgp
echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/18.04/prod bionic main" |  tee /etc/apt/sources.list.d/msftUbuntu1804Prod.list
apt-get update -o Dir::Etc::sourcelist="sources.list.d/msftUbuntu1804Prod.list" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0" 

# Give _apt user ownership of /acms dir to perform apt-get download 
chown -R _apt:root /acms

# Download the ACMS client
apt-get download acms-client=5.8
dpkg --unpack acms-client*.deb

rm acms-client*.deb

# Remove the Post-Install script and cron job
rm /var/lib/dpkg/info/acms-client.postinst -f
rm /etc/cron.daily/acms-client_maintenance

ln -f -s /usr/lib/x86_64-linux-gnu/libIaaSBootstrapper.so.1.0.0 /usr/lib/x86_64-linux-gnu/libIaaSBootstrapper.so.1

dpkg --configure acms-client