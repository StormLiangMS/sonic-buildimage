# docker image for gbsyncd


DOCKER_GBSYNCD_BASE_STEM = docker-gbsyncd-$(DOCKER_GBSYNCD_PLATFORM_CODE)
DOCKER_GBSYNCD_BASE = $(DOCKER_GBSYNCD_BASE_STEM).gz
DOCKER_GBSYNCD_BASE_DBG = $(DOCKER_GBSYNCD_BASE_STEM)-$(DBG_IMAGE_MARK).gz

$(DOCKER_GBSYNCD_BASE)_PATH = $(PLATFORM_PATH)/docker-gbsyncd-$(DOCKER_GBSYNCD_PLATFORM_CODE)

$(DOCKER_GBSYNCD_BASE)_FILES += $(SUPERVISOR_PROC_EXIT_LISTENER_SCRIPT)

$(DOCKER_GBSYNCD_BASE)_LOAD_DOCKERS += $(DOCKER_CONFIG_ENGINE_BUSTER)

$(DOCKER_GBSYNCD_BASE)_DBG_DEPENDS += $($(DOCKER_CONFIG_ENGINE_BUSTER)_DBG_DEPENDS)

$(DOCKER_GBSYNCD_BASE)_DBG_IMAGE_PACKAGES = $($(DOCKER_CONFIG_ENGINE_BUSTER)_DBG_IMAGE_PACKAGES)

SONIC_DOCKER_IMAGES += $(DOCKER_GBSYNCD_BASE)
SONIC_BUSTER_DOCKERS += $(DOCKER_GBSYNCD_BASE)
SONIC_INSTALL_DOCKER_IMAGES += $(DOCKER_GBSYNCD_BASE)

SONIC_DOCKER_DBG_IMAGES += $(DOCKER_GBSYNCD_BASE_DBG)
SONIC_BUSTER_DBG_DOCKERS += $(DOCKER_GBSYNCD_BASE_DBG)
SONIC_INSTALL_DOCKER_DBG_IMAGES += $(DOCKER_GBSYNCD_BASE_DBG)

$(DOCKER_GBSYNCD_BASE)_CONTAINER_NAME = gbsyncd
$(DOCKER_GBSYNCD_BASE)_RUN_OPT += --net=host --privileged -t
$(DOCKER_GBSYNCD_BASE)_RUN_OPT += -v /host/machine.conf:/etc/machine.conf
$(DOCKER_GBSYNCD_BASE)_RUN_OPT += -v /etc/sonic:/etc/sonic:ro
