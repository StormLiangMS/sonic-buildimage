# docker image for fpm

VAS_CLNT = vasclnt_4.1.0-22547_amd64.deb
$(VAS_CLNT)_URL = "https://sonicstorage.blob.core.windows.net/packages/vasclnt_4.1.0-22547_amd64.deb?sv=2015-04-05&sr=b&sig=LahFpjR33OlULAlS9a%2FrpTVNGalFxqFc5Byx9A74tjM%3D&se=2154-03-07T02%3A12%3A35Z&sp=r"

VAS_GP = vasgp_4.1.0-22547_amd64.deb
$(VAS_GP)_URL = "https://sonicstorage.blob.core.windows.net/packages/vasgp_4.1.0-22547_amd64.deb?sv=2015-04-05&sr=b&sig=3%2BM3Sk2c2x5SjCU0Gbtl3xQ7xkelysZgOhxtScDm1lw%3D&se=2154-03-07T02%3A13%3A06Z&sp=r"

SONIC_ONLINE_DEBS += $(VAS_CLNT) $(VAS_GP)

DOCKER_VAS = docker-vas.gz
$(DOCKER_VAS)_PATH = $(DOCKERS_PATH)/docker-vas
$(DOCKER_VAS)_DEPENDS += $(VAS_CLNT) $(VAS_GP)
$(DOCKER_VAS)_LOAD_DOCKERS += $(DOCKER_CONFIG_ENGINE)
SONIC_DOCKER_IMAGES += $(DOCKER_VAS)
SONIC_INSTALL_DOCKER_IMAGES += $(DOCKER_VAS)

$(DOCKER_VAS)_CONTAINER_NAME = vas
$(DOCKER_VAS)_RUN_OPT += --net=host --privileged -t
$(DOCKER_VAS)_RUN_OPT += -v /etc/sonic:/etc/sonic:ro
$(DOCKER_VAS)_RUN_OPT += -v /lib/x86_64-linux-gnu/:/host/lib/x86_64-linux-gnu/:rw
$(DOCKER_VAS)_RUN_OPT += -v /etc/pam.d/:/etc/pam.d/:rw
$(DOCKER_VAS)_RUN_OPT += -v /etc/:/host/etc/:rw
$(DOCKER_VAS)_RUN_OPT += -v /var/opt/quest/vas/vasd/:/var/opt/quest/vas/vasd/:rw
$(DOCKER_VAS)_RUN_OPT += -v /home/:/home/:rw

$(DOCKER_VAS)_BASE_IMAGE_FILES += join_domain:/usr/bin/join_domain

