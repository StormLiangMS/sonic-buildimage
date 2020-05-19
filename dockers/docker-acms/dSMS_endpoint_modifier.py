#!/usr/bin/env python
'''
This script will continuously monitor if ACMS is using the right dSMS endpoint. It will try to point
ACMS to use the correct regional dSMS endpoint and if ACMS fails with the regional endpoint, it will
fall-back to global endpoint and vice-versa.
'''
import os, subprocess, time
from datetime import datetime, timedelta
from sonic_daemon_base.daemon_base import Logger
from swsscommon import swsscommon

# Bootstrap cert
boostrap_cert = "/etc/sonic/credentials/sonic_acms_bootstrap.pfx"
# dSMS config file
dsms_conf = "/var/opt/msft/client/dsms.conf"
# ACMS config file
acms_conf = "/var/opt/msft/client/acms_secrets.ini"
# Acceptable time difference between now and next ACMS poll event for meddling with ACMS config file
time_margin = timedelta(seconds=1800)
# Sleep timer for bootstrapping
bootstrap_alarm = 30

# Redis DB information
REDIS_TIMEOUT_MS = 0

logger = Logger()

def get_device_region():
    config_db = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MS, True)
    device_metadata = swsscommon.Table(config_db, swsscommon.CFG_DEVICE_METADATA_TABLE_NAME)
    (status, tuples) = device_metadata.get("localhost")
    localhost = dict(tuples)
    return localhost['region']

def restore_acms_config_file():
    '''
    Restore the modified ACMS config file with the default one that was shipped with the image
    '''
    cmd = "cp /acms/acms_secrets.ini /var/opt/msft/client/"
    response = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = response.communicate()
    if (response.returncode != 0):
        logger.log_error(stderr)
        return False
    else:
        return True

def change_endpoint_to_regional(acms_conf, region):
    '''
    Change the dSMS endpoint from global (default) to regional
    '''
    acms_conf_file = open(acms_conf, "r+")
    contents = acms_conf_file.read()
    acms_conf_file.write(contents.replace("global", region))
    contents = acms_conf_file.read()
    acms_conf_file.close()
    if (region in contents) and ("global" not in contents):
        return True
    else:
        return False

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

def check_and_modify_endpoint():
    '''
    Rotates between global and regional dSMS endpoints for ACMS when necessary
    '''
    region = get_device_region()
    while True:
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
                                logger.log_debug("dSMS endpoint changed from regional to global")
                        else:
                            logger.log_info("dSMS endpoint is set to regional and last poll was success")
                    else:
                        if change_endpoint_to_regional(acms_conf, region):
                            logger.log_debug("dSMS endpoint changed from global to regional")
                else:
                    logger.log_debug("Skipping dSMS endpoint modification because next poll event is approaching")
                alarm = duration+time_margin
                time.sleep(alarm.total_seconds())
            else:
                # Bootstrap attempt failed
                if regional:
                    if restore_acms_config_file():
                        logger.log_debug("dSMS endpoint changed from regional to global")
                else:
                    if change_endpoint_to_regional(acms_conf, region):
                       logger.log_debug("dSMS endpoint changed from global to regional")
                time.sleep(bootstrap_alarm)
        else:
            # Has not been bootstrapped
            if change_endpoint_to_regional(acms_conf, region):
                logger.log_debug("dSMS endpoint changed from global to regional")
            time.sleep(bootstrap_alarm)

if __name__ == '__main__':
    # Sleep until bootstrap cert is available
    while not os.path.isfile(boostrap_cert):
        time.sleep(60)
        logger.log_info("Waiting for bootstrap cert")

    check_and_modify_endpoint()