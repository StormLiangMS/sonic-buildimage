# docker image for acms

DOCKER_ACMS_STEM = docker-acms
DOCKER_ACMS = $(DOCKER_ACMS_STEM).gz

$(DOCKER_ACMS)_PATH = $(DOCKERS_PATH)/$(DOCKER_ACMS_STEM)

$(DOCKER_ACMS)_PYTHON_WHEELS += $(SONIC_DAEMON_BASE_PY2)

ifeq ($(ENABLE_ACMS), y)
SONIC_DOCKER_IMAGES += $(DOCKER_ACMS)
SONIC_STRETCH_DOCKERS += $(DOCKER_ACMS)
SONIC_INSTALL_DOCKER_IMAGES += $(DOCKER_ACMS)
endif

$(DOCKER_ACMS)_CONTAINER_NAME = acms
$(DOCKER_ACMS)_RUN_OPT += --privileged -t
$(DOCKER_ACMS)_RUN_OPT += -v /etc/sonic/certificates:/etc/sonic/certificates:rw
$(DOCKER_ACMS)_RUN_OPT += -v /var/opt/msft:/var/opt/msft:rw
