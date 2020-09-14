#!/usr/bin/env python
'''
This script will continuously monitor if ACMS is using the right dSMS endpoint. It will try to point
ACMS to use the correct regional dSMS endpoint and if ACMS fails with the regional endpoint, it will
fall-back to global endpoint and vice-versa.
'''
import os, subprocess, time, re
from datetime import datetime, timedelta
from sonic_py_common import logger
from swsscommon import swsscommon

# Bootstrap cert
boostrap_cert = "/etc/sonic/credentials/sonic_acms_bootstrap.pfx"
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

def restore_acms_config_file():
    '''
    Restore the modified ACMS config file with the default one that was shipped with the image
    '''
    cmd = "cp /acms/acms_secrets.ini /var/opt/msft/client/"
    response = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = response.communicate()
    if (response.returncode != 0):
        sonic_logger.log_error(stderr)
        return False
    else:
        return True

def change_endpoint_to_regional(acms_conf, region):
    '''
    Change the dSMS endpoint from global (default) to regional
    '''
    acms_conf_file = open(acms_conf, "r+")
    contents = acms_conf_file.read()
    new_contents = re.sub("global", region, contents)
    acms_conf_file.seek(0)
    acms_conf_file.write(new_contents)
    acms_conf_file.close()
    return

def parse_dsms_conf(dsms_conf):
    bootstrap_status = False
    last_poll_success = False
    next_poll_utc = None
    dsms_conf_file = open(dsms_conf, "r")
    lines = dsms_conf_file.readlines()
    dsms_conf_file.close()
    for line in lines:
        if "HasBootstrapped=yes" in line:
            bootstrap_status = True
        if "LastPollSuccess=yes" in line:
            last_poll_success = True
        if "NextPollUtc" in line:
            date_time = line.split("=")[1]
            date_time = date_time.strip()
            next_poll_utc = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S')
    return bootstrap_status, last_poll_success, next_poll_utc

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
        url_pattern = "https://global-dsms.dsms.core.usgovcloudapi.net"
    elif cloud.lower() == "BlackForest".lower():
        url_pattern = "https://global-dsms.dsms.core.cloudapi.de"
    elif cloud.lower() == "Mooncake".lower():
        url_pattern = "https://global-dsms.dsms.core.chinacloudapi.cn"
    else:
        sonic_logger.log_error("CloudType "+cloud+" not listed!")
        return False
    sonic_logger.log_info("dSMS endpoint for "+cloud+" is "+url_pattern)
    # Change URL pattern in the ACMS config file
    update_dsms_url(acms_conf, url_pattern)
    # Change URL pattern in the original ACMS config file 
    update_dsms_url(acms_conf_ori, url_pattern)
    return True

def check_and_modify_endpoint():
    '''
    Rotates between global and regional dSMS endpoints for ACMS when necessary
    '''
    while True:
        region = get_device_region()
        if os.path.isfile(dsms_conf):
            bootstrap_status, last_poll_success, next_poll_utc = parse_dsms_conf(dsms_conf)
            acms_conf_file = open(acms_conf, "r")
            contents = acms_conf_file.read()
            acms_conf_file.close()
            regional = False
            # Check if current dSMS endpoint is regional or fall-back URL
            if region in contents:
                regional = True
            if bootstrap_status:
                now_utc = datetime.utcnow()
                duration = next_poll_utc - now_utc
                # Meddle with ACMS config file only if we have sufficient time until the next poll event
                if duration > time_margin:
                    if regional:
                        if not last_poll_success:
                            # Last poll was unsuccessful, so try fall-back URL
                            if restore_acms_config_file():
                                sonic_logger.log_debug("dSMS endpoint changed from regional to global")
                        else:
                            sonic_logger.log_info("dSMS endpoint is set to regional and last poll was success")
                    else:
                        if region != "None":
                            change_endpoint_to_regional(acms_conf, region)
                            sonic_logger.log_debug("dSMS endpoint changed from global to regional")
                        else:
                            sonic_logger.log_debug("Failed to obtain region. Skipping endpoint change")
                else:
                    sonic_logger.log_debug("Skipping dSMS endpoint modification because next poll event is approaching")
                alarm = duration+time_margin
                time.sleep(alarm.total_seconds())
            else:
                # Bootstrap attempt failed
                if regional:
                    if restore_acms_config_file():
                        sonic_logger.log_debug("dSMS endpoint changed from regional to global")
                else:
                    if region != "None":
                        change_endpoint_to_regional(acms_conf, region)
                        sonic_logger.log_debug("dSMS endpoint changed from global to regional")
                    else:
                        sonic_logger.log_debug("Failed to obtain region. Skipping endpoint change")
                time.sleep(bootstrap_alarm)
        else:
            # Has not been bootstrapped
            if region != "None":
                change_endpoint_to_regional(acms_conf, region)
                sonic_logger.log_debug("dSMS endpoint changed from global to regional")
            else:
                sonic_logger.log_debug("Failed to obtain region. Skipping endpoint change")
            time.sleep(bootstrap_alarm)

if __name__ == '__main__':
    # Sleep until bootstrap cert is available
    while not os.path.isfile(boostrap_cert):
        time.sleep(60)
        sonic_logger.log_info("Waiting for bootstrap cert")

    cloud = get_device_cloudtype()
    if cloud.lower() != "Public".lower():
        if not fix_endpoint_for_cloud(cloud):
            sonic_logger.log_error("Fixing endpoint for cloudtype "+cloud+" failed!")
            quit()
    check_and_modify_endpoint()
