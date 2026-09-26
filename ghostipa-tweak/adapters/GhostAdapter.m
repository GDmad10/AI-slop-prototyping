// adapters/GhostAdapter.m — generation router + runtime-safe hook stubs.
// Concrete per-generation method lists MUST come from on-device T1 discovery
// (docs/RESEARCH.md). This file only contains what is safe on every version:
// runtime class lookup, append-only merge helpers, product-page opener.
#import "GhostAdapter.h"
#import "../GhostCore.h"
#import "../GhostGuard.h"
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

@interface GhostAdapter_iOS7_9 : GhostAdapter @end
@interface GhostAdapter_iOS10_12 : GhostAdapter @end
@interface GhostAdapter_iOS13_15 : GhostAdapter @end
@interface GhostAdapter_iOS16Plus : GhostAdapter @end

@implementation GhostAdapter
+ (instancetype)adapterForMajorVersion:(NSInteger)major {
    if (major <= 9) return [[GhostAdapter_iOS7_9 alloc] init];
    if (major <= 12) return [[GhostAdapter_iOS10_12 alloc] init];
    if (major <= 15) return [[GhostAdapter_iOS13_15 alloc] init];
    return [[GhostAdapter_iOS16Plus alloc] init]; // 16+ (17+ untested, same path)
}
- (NSString *)generationName { return @"base"; }
// Looks up a private class WITHOUT crashing when absent (§18/§20).
- (Class)safeClass:(const char *)name {
    Class c = objc_getClass(name);
    if (!c) [[GhostCore shared] log:@"class %s absent on this OS — hook skipped", name];
    return c;
}
- (void)installSearchHookWithBlock:(void(^)(NSString *, NSSet *))onSearch {
    (void)onSearch;
    [[GhostCore shared] log:@"%@: search hook waiting on T1-discovered selector", self.generationName];
}
- (void)appendGhostResults:(NSArray *)ghosts {
    // Append-only contract (§5): the per-generation merge hook drains
    // pendingGhosts AFTER %orig — never reorder/remove Apple's rows.
    self.pendingGhosts = ghosts ?: @[];
    [[GhostCore shared] log:@"%@: staged %lu ghost rows for merge", self.generationName, (unsigned long)self.pendingGhosts.count];
}
- (void)installProductBadgeHook {
    [[GhostCore shared] log:@"%@: badge hook waiting on T1-discovered PDP class", self.generationName];
}
- (void)openProductPageForAppleID:(NSString *)adamID {
    NSString *s = [NSString stringWithFormat:@"itms-apps://itunes.apple.com/app/id%@", adamID];
    NSURL *url = [NSURL URLWithString:s];
    UIApplication *app = [UIApplication sharedApplication];
    // openURL:options:completionHandler: exists only on iOS 10+ — legacy path below.
    if ([app respondsToSelector:@selector(openURL:options:completionHandler:)])
        [app openURL:url options:@{} completionHandler:nil];
    else
        [app openURL:url];
}
@end

@implementation GhostAdapter_iOS7_9
- (NSString *)generationName { return @"iOS7-9"; }
- (void)installSearchHookWithBlock:(void(^)(NSString *, NSSet *))onSearch {
    [self safeClass:"AppStore.SearchViewController"]; // VERIFY via T1; nil-safe
    [super installSearchHookWithBlock:onSearch];
}
@end
@implementation GhostAdapter_iOS10_12
- (NSString *)generationName { return @"iOS10-12"; }
@end
@implementation GhostAdapter_iOS13_15
- (NSString *)generationName { return @"iOS13-15"; }
@end
@implementation GhostAdapter_iOS16Plus
- (NSString *)generationName { return @"iOS16+"; }
- (void)installSearchHookWithBlock:(void(^)(NSString *, NSSet *))onSearch {
    // StoreKit 2 path: hook the list view-model delivery, constructed from the
    // same lookup payload (same id, same displayPrice) — never synthesized.
    [self safeClass:"AppStore.SearchResultsViewModel"]; // VERIFY via T1; nil-safe
    [super installSearchHookWithBlock:onSearch];
}
@end
