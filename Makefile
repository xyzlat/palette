PKG1 = akiri.framework_0.5.6_all.deb
PKG2 = proxytunnel_1.9.0%2Bsvn250-5_amd64.deb
PKG2_LINUX_NAME = proxytunnel_1.9.0+svn250-5_amd64.deb
POOL_DIR = dpkg/pool
DOWNLOAD_DIR1 = https://www.akirisolutions.com/download/framework
DOWNLOAD_DIR2 = https://www.akirisolutions.com/download/palette
PREBUILT_PACKAGES = $(POOL_DIR)/$(PKG1) $(POOL_DIR)/$(PKG2)

all: palette controller palette-agent palette-support myip

publish-release: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/release

publish-early: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/early

publish-dev: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/dev

publish-dev2: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/dev2

publish-dev3: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/dev3

publish-sc: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/sc

publish-pro: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/pro

publish-square: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/square

publish-tlc: $(PREBUILT_PACKAGES)
	make clean all
	GNUPGHOME=dpkg/keys reprepro -b dpkg/apt includedeb stable dpkg/pool/*.deb
	chmod 600 dpkg/client/id_rsa; cd dpkg/apt; scp -r -i ../client/id_rsa -r . ubuntu@apt.palette-software.com:/var/packages/tlc

$(POOL_DIR)/$(PKG1):
	wget -N --directory-prefix=$(POOL_DIR) $(DOWNLOAD_DIR1)/$(PKG1)

$(POOL_DIR)/$(PKG2):
	wget -N --directory-prefix=$(POOL_DIR) $(DOWNLOAD_DIR2)/$(PKG2)

palette:
	make -C app all
.PHONY: palette

controller:
	make -C controller all
.PHONY: controller

palette-agent:
	make -C ../palette-agent all
.PHONY: palette-agent

palette-support:
	make -C ../palette-support all
.PHONY: palette-support

myip:
	make -C ../myip
.PHONY: myip

debian:
	make -C controller debian
	make -C app debian

pylint:
	pylint --version
	make -C controller pylint
	make -C app pylint
.PHONY: pylint

clean:
	make -C app clean
	make -C controller clean
	rm -rf dpkg/dists dpkg/pool/*controller* dpkg/pool/*palette* dpkg/apt/db dpkg/apt/dists dpkg/apt/pool
.PHONY: clean

build-setup:
	sudo apt-get install -y debhelper reprepro python-setuptools pylint python-passlib python-tz
	sudo apt-get install -y python-dateutil python-crypto python-boto
	sudo apt-get install -y python-netifaces
	sudo apt-get install -y npm nodejs-legacy
	sudo npm install -g less
	sudo npm install -g grunt-cli
	sudo npm install -g bower
	cd app; sudo ../scripts/setup.sh

.PHONY: build-setup
