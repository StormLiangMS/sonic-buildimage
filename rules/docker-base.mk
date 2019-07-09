# docker base image

DOCKER_BASE = docker-base.gz
$(DOCKER_BASE)_PATH = $(DOCKERS_PATH)/docker-base
$(DOCKER_BASE)_DEPENDS += $(SUPERVISOR)
$(DOCKER_BASE)_DEPENDS += $(BASH)
$(DOCKER_BASE)_DEPENDS += $(SOCAT)

GDB = gdb
VIM = vim
OPENSSH = openssh-client
SSHPASS = sshpass
STRACE = strace
$(DOCKER_BASE)_DBG_IMAGE_PACKAGES += $(GDB) $(VIM) $(OPENSSH) $(SSHPASS) $(STRACE)

SONIC_DOCKER_IMAGES += $(DOCKER_BASE)
