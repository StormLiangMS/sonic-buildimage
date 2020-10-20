# sfputil.py
#
# Platform-specific SFP transceiver interface for SONiC
#

try:
    import time
    from cisco_sfp.sfputilcisco import SfpUtilCisco
    from sonic_eeprom import eeprom_dts
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

class SfpUtil(SfpUtilCisco):
    """Platform-specific SfpUtil class"""

    PORT_START = 0
    PORT_END = 63
    PORTS_IN_BLOCK = 64

    XCVR_PRESENCE_FILE = "/sys/class/mifpga/mifpga/xcvr_present"

    EEPROM_OFFSET = 50

    _port_to_eeprom_mapping = {}

    @property
    def port_start(self):
        return self.PORT_START

    @property
    def port_end(self):
        return self.PORT_END

    @property
    def qsfp_ports(self):
        return range(0, self.PORTS_IN_BLOCK + 1)

    @property
    def port_to_eeprom_mapping(self):
        return self._port_to_eeprom_mapping

    def __init__(self):
        eeprom_path = "/sys/class/i2c-adapter/i2c-{0}/{0}-0050/eeprom"

        for x in range(0, self.PORT_END + 1):
            self._port_to_eeprom_mapping[x] = eeprom_path.format(x + self.EEPROM_OFFSET)

        super(SfpUtil, self).__init__()

    def get_presence(self, port_num):
        # Check for invalid port_num
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False

        port_present="/sys/class/mifpga/mifpga/qsfp_%d_present/value" % (port_num+1)
        present = False
        with open(port_present, "r") as x_p_fp:
            xcvr_line = x_p_fp.readline()   ## Only one line of 0 & 1
            present = int(xcvr_line.strip())
        return present

        '''
        with open(self.XCVR_PRESENCE_FILE, "r") as x_p_fp:
            xcvr_line = x_p_fp.readlines()[0]   ## Only one line of 0 & 1
            xcvrs = [ int(c) for c in xcvr_line.strip() ]
            if xcvrs[port_num-1]:
                return True
        except:
            print "Failed to open", self.XCVR_PRESENCE_FILE
        '''

    def reset(self, port_num):
        # Check for invalid port_num
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False

        port_reset="/sys/class/mifpga/mifpga/qsfp_%d_reset/value" % (port_num+1)
        with open(port_reset, "w") as x_p_fp:
            x_p_fp.write("1")
            x_p_fp.close()
        time.sleep(1)
        with open(port_reset, "w") as x_p_fp:
            x_p_fp.write("0")
            x_p_fp.close()
        return True

    def get_low_power_mode(self, port_num):
        # Check for invalid port_num
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False
        port_lpmode="/sys/class/mifpga/mifpga/qsfp_%d_lp_mode/value" % (port_num+1)
        mode = False
        with open(port_lpmode, "r") as x_p_fp:
            xcvr_line = x_p_fp.readline()   ## Only one line of 0 & 1
            mode = int(xcvr_line.strip())
        return True if mode else False

    def set_low_power_mode(self, port_num, lpmode):
        # Check for invalid port_num
        if port_num < self.PORT_START or port_num > self.PORT_END:
            return False
        port_lpmode="/sys/class/mifpga/mifpga/qsfp_%d_lp_mode/value" % (port_num+1)
        with open(port_lpmode, "w") as x_p_fp:
            x_p_fp.write("1" if lpmode else "0")
        return True

