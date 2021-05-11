# configDB helper functions

from swsscommon import swsscommon
import netaddr
from sonic_py_common import logger

#
# Config
#

DEFAULT_TCP_PORT = 1021
DEFAULT_VXLAN_PORT = 65330
DEFAULT_TCP_OPTIONS = 253
DEFAULT_TTL = 2
REDIS_TIMEOUT_MS = 0
CFG_VLAN_TABLE_NAME = 'VLAN'
CFG_VLAN_VLANID_KEY_NAME = 'vlanid'
CFG_VLAN_MONVLAN_KEY_NAME = 'host_ifname'
CFG_METADATA_LOCALHOST_ENTRY_NAME = 'localhost'
CFG_METADATA_MAC_KEY_NAME = 'mac'

#
# Global logger instance
#
vnetlogger = logger.Logger()


###

#
# Get an ipv4 address from a given string.
# Return None if the given string is not a valid ipv4 address.
#

def get_ipv4_address(value):
    if not value:
        return None

    try:
        addr = netaddr.IPNetwork(str(value))
    except (netaddr.NotRegisteredError, netaddr.AddrFormatError, netaddr.AddrConversionError):
        return None

    if addr.version == 4:
        return str(addr.ip)
    else:
        return None

#
# Get a value of a key from ConfigDB's tablename|entry_name
#

def get_configdb_info(table_name, entry_name, key_name):
    ret_value = None
    if entry_name is None or key_name is None:
        return ret_value

    try:
        config_db = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MS, True)
        vlan_table = swsscommon.Table(config_db, table_name)
        (status, tuples) = vlan_table.get(entry_name)
        entry_info = dict(tuples)
        ret_value = entry_info[key_name]
    except KeyError as ke:
        vnetlogger.log_error("KeyError {0}".format(str(ke)))

    return ret_value

#
# Extract Loopback0 ipv4 address
#

def get_loopback_ipv4():
    loopback0_ipv4 = None

    try:
        config_db = swsscommon.DBConnector("CONFIG_DB", REDIS_TIMEOUT_MS, True)
        loopback_interface = swsscommon.Table(config_db, swsscommon.CFG_LOOPBACK_INTERFACE_TABLE_NAME)
        for loopback in loopback_interface.getKeys():
            if loopback.startswith("Loopback0|"):
                loopback0_prefix_str = loopback.replace("Loopback0|", "")
                ipv4_address = get_ipv4_address(loopback0_prefix_str)
                if ipv4_address is not None:
                    loopback0_ipv4 = ipv4_address
                    break
    except ValueError as ve:
        vnetlogger.log_error("ValueError {0}".format(str(ve)))

    return loopback0_ipv4


#
# Get the vlanid from Vlan interface name
#

def get_mon_vlan_id(vlan_interface_name):
    return get_configdb_info(CFG_VLAN_TABLE_NAME, vlan_interface_name, CFG_VLAN_VLANID_KEY_NAME)


#
# Get the host ifname from Vlan interface name
#

def get_mon_vlan_host_ifname(vlan_interface_name):
    return get_configdb_info(CFG_VLAN_TABLE_NAME, vlan_interface_name, CFG_VLAN_MONVLAN_KEY_NAME)


#
# Get the dut mac address from DEVICE_METADATA|localhost
#

def get_localhost_mac():
    return get_configdb_info(swsscommon.CFG_DEVICE_METADATA_TABLE_NAME, CFG_METADATA_LOCALHOST_ENTRY_NAME, CFG_METADATA_MAC_KEY_NAME)

