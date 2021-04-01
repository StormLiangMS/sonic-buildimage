#!/usr/bin/env python
'''
This script will determine the correct dSMS region to configure ACMS and update the config file
It will also update the ACMS config file with the bootstrap cert path
'''
import os, sys, subprocess, time, re, fnmatch
from datetime import datetime, timedelta
from sonic_py_common import logger
from swsscommon import swsscommon

# Bootstrap cert
bootstrap_cert = ""
# Bootstrap cert file pattern
bootstrap_cert_pattern = "sonic_acms_bootstrap-*.pfx"
# SONiC credentials directory
sonic_creds_dir = "/etc/sonic/credentials/"
# dSMS config file
dsms_conf = "/var/opt/msft/client/dsms.conf"
# ACMS config file
acms_conf = "/var/opt/msft/client/acms_secrets.ini"
# ACMS config file original
acms_conf_ori = "/acms/acms_secrets.ini"
# Acceptable time difference between now and next ACMS poll event for meddling with ACMS config file
time_margin = timedelta(seconds=1800)
# Sleep timer for bootstrapping
bootstrap_alarm = 30

# Redis DB information
REDIS_TIMEOUT_MS = 0

sonic_logger = logger.Logger()
sonic_logger.set_min_log_priority_info()

def get_device_region():
    config_db = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MS, True)
    device_metadata = swsscommon.Table(config_db, swsscommon.CFG_DEVICE_METADATA_TABLE_NAME)
    (status, tuples) = device_metadata.get("localhost")
    localhost = dict(tuples)
    return localhost['region']

def get_device_cloudtype():
    config_db = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MS, True)
    device_metadata = swsscommon.Table(config_db, swsscommon.CFG_DEVICE_METADATA_TABLE_NAME)
    (status, tuples) = device_metadata.get("localhost")
    localhost = dict(tuples)
    return localhost['cloudtype']

def get_device_region_from_bootstrap_cert():
    region = bootstrap_cert.split('-')[1].split('.')[0]
    return region

def update_dsms_url(conf_file, new_url):
    '''
    Update the dSMS URL in the given config file by looking for line starting with FullHttpsDsmsUrl pattern
    '''
    conf_file_t = open(conf_file, "r+")
    contents = conf_file_t.read()
    if new_url not in contents:
        new_contents = re.sub("FullHttpsDsmsUrl=.*", "FullHttpsDsmsUrl="+new_url, contents)
        conf_file_t.seek(0)
        conf_file_t.write(new_contents)
    conf_file_t.close()
    return

def fix_endpoint_for_cloud(cloud):
    '''
    Identify the correct URL pattern for dSMS endpoints in national clouds 
    '''
    # Convert cloudtype to lowercase for case-insensitive string comparison
    if cloud.lower() == "FairFax".lower():
        url_pattern = "https://region-dsms.dsms.core.usgovcloudapi.net"
    elif cloud.lower() == "BlackForest".lower():
        url_pattern = "https://region-dsms.dsms.core.cloudapi.de"
    elif cloud.lower() == "Mooncake".lower():
        url_pattern = "https://region-dsms.dsms.core.chinacloudapi.cn"
    else:
        sonic_logger.log_error("CloudType "+cloud+" not listed!")
        return False
    sonic_logger.log_info("dSMS endpoint for "+cloud+" is "+url_pattern)
    # Change URL pattern in the ACMS config file
    update_dsms_url(acms_conf, url_pattern)
    # Change URL pattern in the original ACMS config file 
    update_dsms_url(acms_conf_ori, url_pattern)
    return True

def update_config():
    '''
    Determine the correct dSMS endpoint and update the ACMS config file
    '''
    region = get_device_region_from_bootstrap_cert()
    acms_conf_file = open(acms_conf, "r+")
    contents = acms_conf_file.read()
    if region not in contents:
        new_contents = re.sub("region", region, contents)
        new_contents = re.sub("BootstrapCert=.*\n*", "BootstrapCert="+sonic_creds_dir+bootstrap_cert+"\n", new_contents)
        sonic_logger.log_info("Updated config: "+new_contents)
        acms_conf_file.seek(0)
        acms_conf_file.write(new_contents)
        sonic_logger.log_debug("dSMS endpoint set to "+region)
    acms_conf_file.close()

if __name__ == '__main__':
    # Sleep until bootstrap cert is available
    bootstrap = False
    while bootstrap == False:
        for file_t in os.listdir(sonic_creds_dir):
            if fnmatch.fnmatch(file_t, bootstrap_cert_pattern):
                bootstrap_cert = file_t
                sonic_logger.log_info("Bootstrap cert found: "+file_t)
                bootstrap = True
                cloud = get_device_cloudtype()
                if cloud.lower() != "Public".lower():
                    if not fix_endpoint_for_cloud(cloud):
                        sonic_logger.log_error("Fixing endpoint for cloudtype "+cloud+" failed!")
                        sys.exit(1)
                update_config()
                sonic_logger.log_info("ACMS Config update complete")
                sys.exit(0)
        sonic_logger.log_info("Waiting for bootstrap cert")
        time.sleep(60)
