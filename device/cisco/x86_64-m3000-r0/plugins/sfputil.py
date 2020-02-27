# sfputil.py
#
# Platform-specific SFP transceiver interface for SONiC
#

try:
    import time
    from sonic_sfp.sfputilbase import SfpUtilBcmMdio
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))


class SfpUtil(SfpUtilBcmMdio):
    """Platform-specific SfpUtil class"""

    PORT_START = 0
    PORT_END = 31
    PORTS_IN_BLOCK = 32

    @property
    def port_start(self):
        return self.PORT_START

    @property
    def port_end(self):
        return self.PORT_END

    @property
    def qsfp_ports(self):
        return range(0, self.PORTS_IN_BLOCK + 1)

    def __init__(self):
        SfpUtilBcmMdio.__init__(self)

    def get_transceiver_change_event(self, timeout=0):
        return True, {}

    def get_presence(self, port_num):
        BCM_USD_PHY_MOD_ABS_INPUT_REG = 0x1c82f
        PRESENCE_MASK = (1 << 6)

        phy_addr = None
        bcm_port = None

        ganged_40_by_4 = self.is_physical_port_ganged_40_by_4(port_num)
        if ganged_40_by_4 == 1:
            # In 40G/4 gang mode, the port is by default configured in
            # single mode. To read the individual sfp details, the port
            # needs to be in quad mode. Set the port mode to quad mode
            # for the duration of this function. Switch it back to
            # original state after we are done
            logical_port = self.get_physical_to_logical(port_num)
            gang_phyid = self.get_40_by_4_gangport_phyid(logical_port[0])

            # Set the gang port to quad mode
            chip_mode_reg = 0xc805
            chip_mode_mask = 0x1

            # bcmcmd phy raw c45 <phyid> 1 <mode_reg_addr> <mode_mask>
            # Ex: bcmcmd phy raw c45 0x4 1 0xc805 0x0070
            gang_chip_mode_orig = self._phy_reg_get(gang_phyid, None, chip_mode_reg)
            quad_mode_mask = gang_chip_mode_orig & ~(chip_mode_mask)
            self._phy_reg_set(gang_phyid, None, chip_mode_reg, quad_mode_mask)

            phy_addr = self.get_physical_port_phyid(port_num)[0]

        if phy_addr is None:
            bcm_port = self._get_bcm_port(port_num)

        regval = self._phy_reg_get(phy_addr, bcm_port, BCM_USD_PHY_MOD_ABS_INPUT_REG)

        if ganged_40_by_4 == 1:
            # Restore original ganging mode
            self._phy_reg_set(gang_phyid, bcm_port,
                              chip_mode_reg, gang_chip_mode_orig)

        if (regval & PRESENCE_MASK) == 0:
            return True

        return False

    def get_low_power_mode(self, port_num):
        print "Low-power mode currently not supported for this platform"
        raise NotImplementedError

    def set_low_power_mode(self, port_num, lpmode):
        print "Low-power mode currently not supported for this platform"
        raise NotImplementedError

    def reset(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            print "Error: Invalid port"
            return False

        qsfp_reset_direction_device_file_path = "/etc/gpiomap/qsfp/qsfp{0}_reset_direction".format(port_num)

        try:
            direction_file = open(qsfp_reset_direction_device_file_path, "w")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        # First, set the direction to 'out' to enable writing value
        direction_file.write("out")
        direction_file.close()

        qsfp_reset_value_device_file_path = "/etc/gpiomap/qsfp/qsfp{0}_reset_value".format(port_num)

        try:
            value_file = open(qsfp_reset_value_device_file_path, "w")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        # Write "1" to put the transceiver into reset mode
        value_file.write("1")
        value_file.close()

        # Sleep 1 second to allow it to settle
        time.sleep(1)

        try:
            value_file = open(qsfp_reset_value_device_file_path, "w")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        # Write "0" to take the transceiver out of reset mode
        value_file.write("0")
        value_file.close()

        return True
