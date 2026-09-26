// Tweak.x — Ghost IPA entry. Minimum necessary hooks (§19): search merge,
// product badge, ghost:// URL. Downloads/install daemons NEVER touched (§12).
#import <UIKit/UIKit.h>
#import "GhostCore.h"
#import "GhostDB.h"
#import "GhostScan.h"
#import "GhostBadge.h"
#import "GhostGuard.h"
#import "GhostCompat.h"
#import "adapters/GhostAdapter.h"

GhostAdapter *ghostAdapter = nil; // global: MergeHooks.x consumes it once T1 names land

%ctor {
    @autoreleasepool {
        NSString *bid = [[NSBundle mainBundle] bundleIdentifier] ?: @"";
        GhostCore *core = [GhostCore shared];
        if (![core boolForKey:kGhostEnabled default:YES]) return;
        // Only live inside the App Store (or Prefs for the companion list).
        BOOL inStore = [bid isEqualToString:@"com.apple.AppStore"];
        BOOL inPrefs = [bid isEqualToString:@"com.apple.Preferences"];
        if (!inStore && !inPrefs) return;
        ghostAdapter = [GhostAdapter adapterForMajorVersion:GhostSystemMajorVersion()];
        [core log:@"loaded in %@, adapter=%@", bid, ghostAdapter.generationName];
        BOOL experimental = [core boolForKey:kGhostExperimental default:NO];
        if (experimental && ![GhostGuard experimentalHooksAllowed]) {
            [core log:@"experimental hooks suppressed after crashes — running safe hooks only"];
            experimental = NO;
        }
        __weak typeof(ghostAdapter) weakA = ghostAdapter;
        [ghostAdapter installSearchHookWithBlock:^(NSString *query, NSSet<NSString *> *visible) {
            [[GhostScan shared] scanQuery:query visibleAppleIDs:visible completion:^(NSArray *ghosts) {
                [weakA appendGhostResults:ghosts];
            }];
        }];
        [ghostAdapter installProductBadgeHook];
    }
}

// ghost://app/<adamID> + ghost://bundle/<id> handling (§6).
// Resolution below only opens GENUINE records (§20).
// Modern entry point first (iOS 10+ routes here); legacy kept as fallback.
static BOOL GhostHandleURL(NSURL *url) {
    if (![[url.scheme lowercaseString] isEqualToString:@"ghost"]) return NO;
    GhostApp *g = [[GhostScan shared] resolveGhostURL:url];
    if (g) {
        [ghostAdapter openProductPageForAppleID:g.appleID];
        return YES;
    }
    [[GhostCore shared] log:@"ghost URL with insufficient evidence — not displayed"];
    return NO; // fail-safe: no record, no page (§20)
}
%hook UIApplication
- (BOOL)openURL:(NSURL *)url options:(NSDictionary *)options completionHandler:(void(^)(BOOL))completion {
    if ([[url.scheme lowercaseString] isEqualToString:@"ghost"]) {
        BOOL ok = GhostHandleURL(url);
        if (completion) completion(ok);
        return ok;
    }
    return %orig;
}
- (BOOL)openURL:(NSURL *)url {
    if ([[url.scheme lowercaseString] isEqualToString:@"ghost"])
        return GhostHandleURL(url);
    return %orig;
}
%end
