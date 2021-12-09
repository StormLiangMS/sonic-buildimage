#!/usr/bin/env python

from scapy.all import *
import configutil
from sonic_py_common import logger
import time
from datetime import timedelta

#
# Config
#
PRINT_TO_CONSOLE = False
RESTART_INTERVAL = 60

#
# Global logger instance
#
vnetlogger = logger.Logger()

#
# Setup a TCP ping server
#

def tcpserver(serverport):

    # Send SYNACK packets
    def _ack(packet, flag, seqno, ackno):
        try:
            srcip = packet[IP].src
            dstip = packet[IP].dst

            innerpacket = packet[UDP][Ether]
            srcport = innerpacket[TCP].sport
            dstport = innerpacket[TCP].dport

            # send SYNACK to remote host
            TCP_SYNACK = IP(src=dstip, dst=srcip)/TCP(sport=dstport, dport=srcport, flags=flag, seq=seqno, ack=ackno, options=[(configutil.DEFAULT_TCP_OPTIONS, b'\0')])
            ANSWER = send(TCP_SYNACK, verbose=0)
            vnetlogger.log_info("vnetpingsrv: reply packet {0}.".format(TCP_SYNACK.summary()), PRINT_TO_CONSOLE)
        except IndexError as ie:
            vnetlogger.log_info("vnetpingsrv: IndexError {0}".format(str(ie)))

    # Process packets
    def _processpackets(packet):
        if packet.haslayer(TCP) and packet[TCP].dport == configutil.DEFAULT_TCP_PORT:
            if packet[TCP].flags & 0x02 == 0x02 : # SYNC
                seqno = random.randrange(0, (2**32)-1)
                ackno = packet[TCP].seq + 1
                _ack(packet, "SA", seqno, ackno)

            if packet[TCP].flags & 0x08 == 0x08 : # PSH
                seqno = packet[TCP].seq + 1
                ackno = packet[TCP].seq + len(packet[Raw])
                _ack(packet, "A", seqno, ackno)

    vnetlogger.log_info("vnetpingsrv: vnetping server starts.")
    loopbackip = configutil.get_loopback_ipv4()
    # Wait for client to connect.
    sniffstring = "udp and dst host " + loopbackip + " and dst port " + str(serverport)
    vnetlogger.log_info("vnetpingsrv: sniff filter is {0}".format(sniffstring), PRINT_TO_CONSOLE)
    pchandler = configutil.PortChannelHandler()
    iface_list = pchandler.get_up_portchannels()
    vnetlogger.log_info("vnetpingsrv: sniff on interfaces -- {0}".format(iface_list), PRINT_TO_CONSOLE)
    
    sniffer = AsyncSniffer(filter=sniffstring, prn=_processpackets, iface=iface_list, store=False)
    sniffer.start()
    starttime = time.time()
    while True:
        msgs = pchandler.wait_for_netlink_msgs()
        if pchandler.sniffer_restart_required(msgs):
            # wait for at least RESTART_INTERVAL seconds to restart the sniffing, to handle flapping cases
            elapsedseconds = timedelta(seconds=(time.time() - starttime)).total_seconds()
            if elapsedseconds < RESTART_INTERVAL:
                time.sleep(RESTART_INTERVAL)

            sniffer.stop()
            iface_list = pchandler.get_up_portchannels()
            sniffer = AsyncSniffer(filter=sniffstring, prn=_processpackets, iface=iface_list, store=False)
            vnetlogger.log_notice('vnetpingsrv:  Restarting sniffing on interfaces -- {0}'.format(iface_list), PRINT_TO_CONSOLE)
            sniffer.start()
            starttime = time.time()


#
# Main function
#

def main():
    vnetlogger.set_min_log_priority_info()
    bind_layers(UDP, VXLAN, sport=configutil.DEFAULT_VXLAN_PORT)
    bind_layers(UDP, VXLAN, dport=configutil.DEFAULT_VXLAN_PORT)
    configutil.vnetlogger.set_min_log_priority_info()
    tcpserver(configutil.DEFAULT_VXLAN_PORT)


#
# Program entry
#

if __name__ == '__main__':
    main()
