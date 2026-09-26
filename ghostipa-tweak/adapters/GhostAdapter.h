// adapters/GhostAdapter.h — generation abstraction (§4, §18). Concrete classes
// resolved at runtime after T1/T2/T3 discovery; selectors below are the *stable
// public* surface. Private AppStore classes are looked up with NSClassFromString
// and verified non-nil before ANY hook installs — never assumed present.
#import <Foundation/Foundation.h>
@class GhostApp;

@interface GhostAdapter : NSObject
@property (nonatomic, copy) NSArray<GhostApp *> *pendingGhosts; // latest scan, drained by merge hook
+ (instancetype)adapterForMajorVersion:(NSInteger)major; // 7..16+, no NSOperatingSystemVersion (iOS 8+)
- (NSString *)generationName;             // @"iOS7-9" / @"iOS10-12" / @"iOS13-15" / @"iOS16+"
- (void)installSearchHookWithBlock:(void(^)(NSString *query, NSSet<NSString *> *visibleIDs))onSearch;
- (void)appendGhostResults:(NSArray<GhostApp *> *)ghosts; // append-only merge (§5)
- (void)installProductBadgeHook;          // 👻 subtitle + status card (§9)
- (void)openProductPageForAppleID:(NSString *)adamID; // itms-apps://…/app/id<adamID>
@end
