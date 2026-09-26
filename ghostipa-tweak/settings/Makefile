BUNDLE_NAME = GhostIPAPrefs
ARCHS = armv7 armv7s arm64 arm64e
TARGET = iphone:clang:latest:7.0
GhostIPAPrefs_INSTALL_PATH = /Library/PreferenceBundles
GhostIPAPrefs_PRIVATE_FRAMEWORKS = Preferences
GhostIPAPrefs_FILES = GhostPrefs.m
GhostIPAPrefs_CFLAGS = -fobjc-arc -Wall -Wextra -Werror

include $(THEOS)/makefiles/common.mk
include $(THEOS_MAKE_PATH)/preference.mk
