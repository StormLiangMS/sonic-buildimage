#!/usr/bin/env python

#############################################################################
# Nexus 3132
#
# Platform and model specific eeprom subclass, inherits from the base class,
# and provides the followings:
# - the eeprom format definition
# - specific encoder/decoder if there is special need
#############################################################################

try:
    import binascii
    import eeprom_tlvinfo
except ImportError, e:
    raise ImportError (str(e) + "- required module not found")

SUP_PID_OFFSET     = 34
SUP_SN_OFFSET      = 54
CARD_INDEX_OFFSET  = 182
PID_OFFSET         = 4130
SN_OFFSET          = 4150
MAC_BASE_OFFSET    = 4280

MAC_ADDR_SIZE       = 6
PRODUCT_NUMBER_SIZE = 20
SERIAL_NUMBER_SIZE  = 20
CARD_INDEX_SIZE     = 2

class board(eeprom_tlvinfo.TlvInfoDecoder):

    _TLV_INFO_MAX_LEN = 8192
    _TLV_HDR_ENABLED = 0

    def __init__(self, name, path, cpld_root, ro):
        self.eeprom_path = "/sys/class/i2c-adapter/i2c-1/1-0052/eeprom"
        super(board, self).__init__(self.eeprom_path, 0, '', True)

    def decode_eeprom(self, e):
        print "TLV Name             Len Value"
        print "-------------------- --- -----"
        print self.dump_info(e, SUP_PID_OFFSET, PRODUCT_NUMBER_SIZE, "Sup-PID:")
        print self.dump_info(e, SUP_SN_OFFSET, SERIAL_NUMBER_SIZE, "Sup-S/N:")
        print self.dump_info(e, CARD_INDEX_OFFSET, CARD_INDEX_SIZE, "Card Index:")
        print self.dump_info(e, PID_OFFSET, PRODUCT_NUMBER_SIZE, "PID:")
        print self.dump_info(e, SN_OFFSET, SERIAL_NUMBER_SIZE, "S/N:")
        print self.dump_mac(e)

    def dump_info(self, e, offset, size, name):
        return "%-20s %3d %s" % (name, size, e[offset:offset+size])

    def dump_mac(self, e):
        mac_base = e[MAC_BASE_OFFSET:MAC_BASE_OFFSET+MAC_ADDR_SIZE]
        mac = ":".join([binascii.b2a_hex(T) for T in mac_base]).upper()
        return "%-20s %3d %s" % ("MAC Base:", 6, mac)

    def is_checksum_valid(self, e):
        return (True, 0)

    def base_mac_addr(self, e):
        mac_base = e[MAC_BASE_OFFSET:MAC_BASE_OFFSET+MAC_ADDR_SIZE]
        return ":".join([binascii.b2a_hex(T) for T in mac_base]).upper()

    def serial_number_str(self, e):
        return e[SN_OFFSET:SN_OFFSET+SERIAL_NUMBER_SIZE]
