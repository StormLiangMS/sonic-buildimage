# sfputil.py
#
# Platform-specific SFP transceiver interface for SONiC
#

try:
    import time
    from sonic_sfp.sfputilbase import SfpUtilBase
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

class SfpUtilCisco(SfpUtilBase):
    """Platform-specific SfpUtil class"""

    XCVR_CHANGE_WAIT_TIME = .2


    _xcvr_presence = None

    EEPROM_OFFSET = 20


    def __init__(self):
        super(SfpUtilCisco, self).__init__()


    def get_transceiver_change_event(self, timeout=0):

        end_time = time.time() + timeout

        p_dict = {}
        while True:
            try:
                xcvrs = [ 1 if ((self.get_presence(p)) == True) else 0 for p in range(0, self.port_end + 1) ]
            except:
                print "Failed to get presence"
                return False, {}

            if self._xcvr_presence is not None:
                # Previous state present. Check any change from previous state
                for p in range(0, self.port_end + 1):
                    if self._xcvr_presence[p] != xcvrs[p]:
                        # Add the change to dict
                        p_dict[str(p)] = str(xcvrs[p])
                        # if inserted then unreset
                        if xcvrs[p] == 1 :
                            self.reset(p)

            self._xcvr_presence = xcvrs
            #print(xcvrs)
            #log_error("XCVR-LOG XCVRS: %s" % str(xcvrs), True)
            # if any change got added to dict in the comparison then return
            if p_dict:
                return True, p_dict

            cur_time = time.time()
            if cur_time >= end_time and timeout != 0:
                break
            elif (cur_time + self.XCVR_CHANGE_WAIT_TIME) >= end_time and timeout != 0:
                time.sleep(end_time - cur_time)
            else:
                time.sleep(self.XCVR_CHANGE_WAIT_TIME)


        return True, {}


class SfpUtil(SfpUtilCisco):
    """Platform-specific SfpUtil class"""

    PORT_START = 0
    PORT_END = 31
    PORTS_IN_BLOCK = 32

    EEPROM_OFFSET = 20

    GPIO_QSFP_RESET_START = 400
    GPIO_QSFP_PRESENCE_START = 432

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

        for x in range(0, self.port_end + 1):
            self._port_to_eeprom_mapping[x] = eeprom_path.format(x + self.EEPROM_OFFSET)

        super(SfpUtil, self).__init__()

    def get_presence(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            print "Error: Invalid port"
            return False

        qsfp_presence_direction_device_file_path = "/sys/class/gpio/gpio{0}/direction".format(self.GPIO_QSFP_PRESENCE_START + port_num)

        try:
            direction_file = open(qsfp_presence_direction_device_file_path, "w")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        # First, set the direction to "in" to enable reading value
        direction_file.write("in")
        direction_file.close()

        qsfp_presence_value_device_file_path = "/sys/class/gpio/gpio{0}/value".format(self.GPIO_QSFP_PRESENCE_START + port_num)

        try:
            value_file = open(qsfp_presence_value_device_file_path, "r")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        content = value_file.readline().rstrip()
        value_file.close()

        if content == "1":
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

        qsfp_reset_direction_device_file_path = "/sys/class/gpio/gpio{0}/direction".format(self.GPIO_QSFP_RESET_START + port_num)

        try:
            direction_file = open(qsfp_reset_direction_device_file_path, "w")
        except IOError as e:
            print "Error: unable to open file: %s" % str(e)
            return False

        # First, set the direction to "out" to enable writing value
        direction_file.write("out")
        direction_file.close()

        qsfp_reset_value_device_file_path = "/sys/class/gpio/gpio{0}/value".format(self.GPIO_QSFP_RESET_START + port_num)

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
