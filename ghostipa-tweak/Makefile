THEOS_DEVICE_IP = 127.0.0.1
THEOS_DEVICE_PORT = 22
ARCHS = armv7 armv7s arm64 arm64e
TARGET = iphone:clang:latest:7.0

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = GhostIPA
GhostIPA_FILES = Tweak.x GhostCore.m GhostDB.m GhostScan.m GhostBadge.m GhostGuard.m GhostPurchased.m adapters/GhostAdapter.m
GhostIPA_CFLAGS = -fobjc-arc -Wall -Wextra -Werror
GhostIPA_FRAMEWORKS = Foundation UIKit

include $(THEOS_MAKE_PATH)/tweak.mk

after-install::
	install.exec "killall -9 AppStore 2>/dev/null; killall -9 Preferences 2>/dev/null; true"

SUBPROJECTS += settings
include $(THEOS_MAKE_PATH)/aggregate.mk
