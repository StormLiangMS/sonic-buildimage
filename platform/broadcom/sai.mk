BRCM_SAI = libsaibcm_3.7.6.1-1_amd64.deb
$(BRCM_SAI)_URL = "https://sonicstorage.blob.core.windows.net/packages/bcmsai/3.7/libsaibcm_3.7.6.1-1_amd64.deb?sv=2015-04-05&sr=b&sig=NQ1hWKi6zjqigwb%2BDhM239G6AhL0HvktYE7FW79VdmY%3D&se=2030-08-03T23%3A01%3A11Z&sp=r"
BRCM_SAI_DEV = libsaibcm-dev_3.7.6.1-1_amd64.deb
$(eval $(call add_derived_package,$(BRCM_SAI),$(BRCM_SAI_DEV)))
$(BRCM_SAI_DEV)_URL = "https://sonicstorage.blob.core.windows.net/packages/bcmsai/3.7/libsaibcm-dev_3.7.6.1-1_amd64.deb?sv=2015-04-05&sr=b&sig=aUS4ZFCfD%2Bct29T%2B0xJAtFHfmtX1dTTsxKTyNtOw1O4%3D&se=2030-08-03T23%3A02%3A56Z&sp=r"

BRCM_SAI_DBG = libsaibcm-dbg_3.7.5.2_amd64.deb
$(eval $(call add_derived_package,$(BRCM_SAI),$(BRCM_SAI_DBG)))
$(BRCM_SAI_DBG)_URL = "https://sonicstorage.blob.core.windows.net/packages/bcmsai/3.7/libsaibcm-dbg_3.7.5.2_amd64.deb?sv=2015-04-05&sr=b&sig=mReW7YrZTTTtGwDVb0x51oDAiOLv2VcJKOwDFkSari0%3D&se=2023-06-25T20%3A17%3A13Z&sp=r"

SONIC_ONLINE_DEBS += $(BRCM_SAI)
$(BRCM_SAI_DEV)_DEPENDS += $(BRCM_SAI)
$(BRCM_SAI_DBG)_DEPENDS += $(BRCM_SAI)
$(eval $(call add_conflict_package,$(BRCM_SAI_DEV),$(LIBSAIVS_DEV)))
