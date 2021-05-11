#!/usr/bin/env python

########################################
#
# Vnet ping
#
########################################


import argparse
import logging
from scapy.all import *
from sys import argv, exit
import configutil
from sonic_py_common import logger

#
# Config
#
PRINT_TO_CONSOLE = True

#
# Global logger instance
#
vnetlogger = logger.Logger()

####

class TcpSession:

    #
    # Initialize an instance.
    #

    def __init__(self,target):
        self.seq = 0
        self.ack = 0
        self.srcip = target[0]
        self.dstip = target[1]
        self.dport = target[2]
        self.vlanid = target[3]
        self.vlanifname = target[4]
        self.loopbackip = target[5]
        self.dutmac = target[6]
        self._ackThread = None
        self._timeout = 3
        self.ip = IP(src=self.srcip, dst=self.dstip)
        self.ttl = configutil.DEFAULT_TTL
        self.sentpackets = 0
        self.receivedpackets = 0
        self.rttms = 0
        self.verbose = 0
        self.random_mac = '00:01:02:03:04:05'


    #
    # Connect to a TCP server.
    #

    def connect(self):
        self.seq = random.randrange(0,(2**32)-1)

        ip = IP(src=self.srcip, dst=self.dstip, ttl=self.ttl)

        tcpsync = Ether(src=self.random_mac, dst=self.dutmac)/ip/TCP(dport=self.dport, seq=self.seq, flags='S', options=[(configutil.DEFAULT_TCP_OPTIONS, b'\0')])
        syn_ack = srp1(tcpsync, iface=self.vlanifname, timeout=self._timeout, verbose=self.verbose)
        self.seq += 1
        self.sentpackets += 1

        if syn_ack:
            self.receivedpackets += 1
            if syn_ack.time and tcpsync.sent_time:
                self.rttms = (syn_ack.time - tcpsync.sent_time) * 1000
                vnetlogger.log_info("Reply from {0}: time={1}.2fms TTL={2}".format(self.dstip, self.rttms, self.ttl), PRINT_TO_CONSOLE)
            else:
                vnetlogger.log_info("Reply from {0}: TTL={1}".format(self.dstip, self.ttl), PRINT_TO_CONSOLE)
        elif self.srcip == self.loopbackip:
            vnetlogger.log_info("Request timed out.", PRINT_TO_CONSOLE)


    #
    # Close a connect to a TCP server.
    #

    def close(self):
        self.seq = random.randrange(0, (2**32)-1)
        ack = self.ip/TCP(dport=self.dport, seq=self.seq, flags='R', options=[(configutil.DEFAULT_TCP_OPTIONS, b'\0')])
        send(ack, verbose = self.verbose)

####


#
# Main function
#

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', dest='vnetname', metavar='vnetname', type=str, required=False, help='Source VNET name to inject packet to')
    parser.add_argument('-i', dest='vnetinterface', metavar='vnetinterface', type=str, required=False, help='VLAN interface name that belongs to vnet_name')
    parser.add_argument('-s', dest='srcip', metavar='srcip', type=str, required=False, help='Overlay source ip')
    parser.add_argument('-d', dest='dstip', metavar='dstip', type=str, required=True, help='Overlay destination ip')
    args = parser.parse_args()

    logging.getLogger("scapy").setLevel(logging.CRITICAL)
    vnetlogger.set_min_log_priority_info()

    vnetname = args.vnetname
    srcip = args.srcip
    dstip = args.dstip
    dstport = configutil.DEFAULT_TCP_PORT
    loopbackip = configutil.get_loopback_ipv4()
    monvlanid = configutil.get_mon_vlan_id(args.vnetinterface)
    monvlanifname = configutil.get_mon_vlan_host_ifname(args.vnetinterface)
    dutmac = configutil.get_localhost_mac()

    if monvlanifname is None:
        vnetlogger.log_error("monvlanifname can't be None", PRINT_TO_CONSOLE)
        sys.exit(1)

    if srcip is None:
        if loopbackip is None:
            vnetlogger.log_error("srcip and loopbackip can't be None in the same time", PRINT_TO_CONSOLE)
            sys.exit(1)
        else:
            srcip = loopbackip

    tcp_hs = TcpSession((srcip, dstip, dstport, monvlanid, monvlanifname, loopbackip, dutmac))

    for x in range(4):
        tcp_hs.connect()
        tcp_hs.close()
        time.sleep(0.5)

    if srcip == loopbackip:
        lostrate = (tcp_hs.sentpackets - tcp_hs.receivedpackets) * 100 / tcp_hs.sentpackets
        vnetlogger.log_info("Ping statistics for {0}:".format(dstip), PRINT_TO_CONSOLE)
        vnetlogger.log_info("    Packets: Sent = {0}, Received = {1}, Lost = {2} ({3}%% loss)".format(tcp_hs.sentpackets, tcp_hs.receivedpackets, lostrate, lostrate), PRINT_TO_CONSOLE)
    else:
        vnetlogger.log_info("{0} packets sent".format(tcp_hs.sentpackets), PRINT_TO_CONSOLE)


#
# Program entry
#

if __name__ == '__main__':
    main(sys.argv[1:])
