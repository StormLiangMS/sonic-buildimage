#!/usr/bin/env python

from scapy.all import *
import configutil
from sonic_py_common import logger

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
            ip = IP(src=dstip, dst=srcip)
            TCP_SYNACK = TCP(sport=dstport, dport=srcport, flags=flag, seq=seqno, ack=ackno, options=[(configutil.DEFAULT_TCP_OPTIONS, b'\0')])
            ANSWER = send(ip / TCP_SYNACK, verbose=0)
        except IndexError as ie:
            vnetlogger.log_info("IndexError {0}".format(str(ie)))

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
    while True:
        sniff(filter=sniffstring, prn=_processpackets)


#
# Main function
#

def main():
    vnetlogger.set_min_log_priority_info()
    bind_layers(UDP, VXLAN, sport=configutil.DEFAULT_VXLAN_PORT)
    bind_layers(UDP, VXLAN, dport=configutil.DEFAULT_VXLAN_PORT)
    tcpserver(configutil.DEFAULT_VXLAN_PORT)


#
# Program entry
#

if __name__ == '__main__':
    main()
