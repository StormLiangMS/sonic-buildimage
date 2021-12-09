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
import threading
import configutil
from sonic_py_common import logger

#
# Config
#
PRINT_TO_CONSOLE = True
PACKET_COUNT = 4
TIMEOUT_SNIFFING = 15
TIMEOUT_INTERVAL = 1
receivedtime = []

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
        self.ttl = configutil.DEFAULT_TTL
        self.verbose = 0
        self.random_mac = '00:01:02:03:04:05'


    #
    # Connect to a TCP server.
    #

    def connect(self, senttime):
        self.seq = random.randrange(0,(2**32)-1)

        ip = IP(src=self.srcip, dst=self.dstip, ttl=self.ttl)
        tcpsync = Ether(src=self.random_mac, dst=self.dutmac)/ip/TCP(dport=self.dport, seq=self.seq, flags='S', options=[(configutil.DEFAULT_TCP_OPTIONS, b'\0')])
        sendp(tcpsync, iface=self.vlanifname, verbose=self.verbose)
        senttime.append(tcpsync.sent_time)
        self.seq += 1

    #
    # Sniffing thread
    #

    def sniff_thread(self):
        def _processpackets(packet):
            global receivedtime
            receivedtime.append(packet.time)
            vnetlogger.log_info("    Reply at {0}: {1}.".format(packet.sniffed_on, packet.summary()), PRINT_TO_CONSOLE)

        loopbackip = configutil.get_loopback_ipv4()
        sniffstring = "tcp and (tcp[tcpflags] & (tcp-syn | tcp-ack) == (tcp-syn | tcp-ack)) and dst host " + loopbackip + " and src port " + str(configutil.DEFAULT_TCP_PORT)
        pchandler = configutil.PortChannelHandler()
        iface_list = pchandler.get_up_portchannels()
        sniff(filter=sniffstring, prn=_processpackets, iface=iface_list, store=False, count=PACKET_COUNT, timeout=TIMEOUT_SNIFFING)

    #
    # Start sniffing thread
    #

    def run_thread(self):
        thread_sniffing = threading.Thread(target=self.sniff_thread)
        thread_sniffing.start()

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
    configutil.vnetlogger.set_min_log_priority_info()

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
    tcp_hs.run_thread()
    senttime = []

    for x in range(PACKET_COUNT):
        time.sleep(TIMEOUT_INTERVAL)
        tcp_hs.connect(senttime)

    time.sleep(TIMEOUT_INTERVAL)
    sentpackets = len(senttime)
    receivedpackets = len(receivedtime)
    lostrate = (sentpackets - receivedpackets) * 100 / sentpackets
    vnetlogger.log_info("Ping statistics for {0}:".format(dstip), PRINT_TO_CONSOLE)
    vnetlogger.log_info("    Packets: Sent = {0}, Received = {1}, Lost = {2} ({3}% loss)".format(sentpackets, receivedpackets, lostrate, lostrate), PRINT_TO_CONSOLE)

#
# Program entry
#

if __name__ == '__main__':
    main(sys.argv[1:])
