#!/usr/bin/env python

try:
    from sonic_sfp.sfputilbase import sfputil_bcm_mdio
except ImportError, e:
    raise ImportError (str(e) + "- required module not found")


class sfputil(sfputil_bcm_mdio):
    """Platform specific sfputil class"""

    port_start = 0
    port_end = 31
    ports_in_block = 32

    _qsfp_ports = range(0, ports_in_block)

    def __init__(self, port_num):
        sfputil_bcm_mdio.__init__(self, port_num)
