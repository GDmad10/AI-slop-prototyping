// GhostPurchased.h — the whole point: past purchases Apple still hosts.
// A ghost in the local DB is evidence of past ownership. This module turns
// that evidence into one-tap redownloads through Apple's OWN controls:
// opening the normal product page (itms-apps://) where Apple renders its own
// cloud-glyph Get button. No downloader, no bypass — the receipt does the work.
#import <Foundation/Foundation.h>
@class GhostApp;

@interface GhostPurchased : NSObject
+ (instancetype)shared;
// Every cached ghost, newest-check first: each is a redownload candidate.
- (NSArray<GhostApp *> *)redownloadCandidates;
// Row title for Purchased-list injection: "name — Tap to redownload".
+ (NSString *)rowTitleForApp:(GhostApp *)app;
// Opens the normal PDP for the ghost. Apple's cloud button does the rest.
- (void)openRedownloadForApp:(GhostApp *)app;
// Summary for prefs/debug: "N owned, M tombstoned, K delisted".
- (NSString *)summaryString;
@end
