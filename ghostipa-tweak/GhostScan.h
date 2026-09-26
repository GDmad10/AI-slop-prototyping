// GhostScan.h — automatic discovery (§8): lookup + storefront sweep, genuine records only.
#import <Foundation/Foundation.h>
@class GhostApp;

typedef void (^GhostScanDone)(NSArray<GhostApp *> *ghosts);

@interface GhostScan : NSObject
+ (instancetype)shared;
// Resolve ghost://app/<adamID> and ghost://bundle/<bundleID> (§6).
- (GhostApp *)resolveGhostURL:(NSURL *)url;
// Main pass: given the user's query + Apple's visible adamIDs, find hidden records.
- (void)scanQuery:(NSString *)query visibleAppleIDs:(NSSet<NSString *> *)visible completion:(GhostScanDone)done;
@end
