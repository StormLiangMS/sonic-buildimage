#!/usr/bin/env python

'''
This script will call dSMS GetIssuers API to download AME Root Certificate
'''

import os, re, shutil
import urllib, urllib2
import json
from sonic_py_common import logger

CERTIFICATE_AUTHORITY = "ame"
API_URL = "https://ussouth-dsms.dsms.core.windows.net/dsms/issuercertificates?getissuersv2"
ROOT_CERT = "/acms/AME_ROOT_CERTIFICATE.pem"
CERTS_PATH = "/etc/sonic/credentials/"

sonic_logger = logger.Logger()

def copy_cert(source, destination_dir):
    # Copy the certificate file from /acms to /etc/sonic/credentials
    if os.path.isfile(source):
        cert_file = os.path.split(source)[1]
        destination = os.path.join(destination_dir, cert_file)
        if os.path.isfile(destination):
            # Delete existing file before copying latest one
            os.remove(destination)
            sonic_logger.log_info("CA_cert_downloader: copy_cert: Existing Root Cert file removed")
        shutil.copyfile(source, destination)
        if os.path.exists(destination):
            return True
        else:
            sonic_logger.log_error("CA_cert_downloader: copy_cert: "+stderr)
            return False
    else:
        sonic_logger.log_error("CA_cert_downloader: copy_cert: File does not exist")
        return False

def extract_cert(response):
    # Extract certificate from the API response
    if os.path.exists(ROOT_CERT):
        os.remove(ROOT_CERT)
    root_cert = open(ROOT_CERT, 'w')
    cert_begin_marker = "-----BEGIN CERTIFICATE-----"
    cert_end_marker = "-----END CERTIFICATE-----"

    root = response['RootsInfos'][0]
    for item in root['Intermediates']:
        root_cert.write(cert_begin_marker+"\n")
        body = re.sub("(.{64})", "\\1\n", item['Body'], 0, re.DOTALL)
        root_cert.write(body+"\n")
        root_cert.write(cert_end_marker+"\n")

    root_cert.write(cert_begin_marker+"\n")
    root_body = re.sub("(.{64})", "\\1\n", root['Body'], 0, re.DOTALL)
    root_cert.write(root_body+"\n")
    root_cert.write(cert_end_marker+"\n")   

    root_cert.close() 

def get_cert(ca, url):
    # Call API and get response
    payload = {'caname': ca}
    url = url+"&"+urllib.urlencode(payload)
    req = urllib2.Request(url)
    response = urllib2.urlopen(req)
    sonic_logger.log_info("CA_cert_downloader: get_cert: URL: "+url)
    if response.getcode() == 200:
        try:
            json_response = json.loads(response.read())
            extract_cert(json_response)
        except ValueError as e:
            sonic_logger.log_error("CA_cert_downloader: get_cert: Invalid JSON response!")
    else:
        sonic_logger.log_error("CA_cert_downloader: get_cert: GET request failed!")
        return False
    return True

def main():
    if get_cert(CERTIFICATE_AUTHORITY, API_URL):
        sonic_logger.log_info("CA_cert_downloader: main: Cert extraction completed")
        if copy_cert(ROOT_CERT, CERTS_PATH):
            sonic_logger.log_info("CA_cert_downloader: main: Root cert moved to "+CERTS_PATH)
        else:
            sonic_logger.log_error("CA_cert_downloader: main: Root cert move to "+CERTS_PATH+" failed!")
    else:
        sonic_logger.log_error("CA_cert_downloader: main: Cert extraction failed!")

if __name__ == '__main__':
    sonic_logger.set_min_log_priority_info()
    main()
