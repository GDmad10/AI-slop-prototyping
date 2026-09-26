// GhostPurchased.m
#import "GhostPurchased.h"
#import "GhostCore.h"
#import "GhostDB.h"
#import "adapters/GhostAdapter.h"

extern GhostAdapter *ghostAdapter;

@implementation GhostPurchased
+ (instancetype)shared {
    static GhostPurchased *s; static dispatch_once_t t;
    dispatch_once(&t, ^{ s = [[self alloc] init]; });
    return s;
}
- (NSArray<GhostApp *> *)redownloadCandidates {
    // Cache = ownership evidence. Tombstoned included: Apple sometimes restores
    // the package while the listing stays dead — the PDP decides, not us.
    NSArray *all = [[GhostDB shared] allGhosts];
    return [all sortedArrayUsingDescriptors:@[[NSSortDescriptor sortDescriptorWithKey:@"lastChecked" ascending:NO]]];
}
+ (NSString *)rowTitleForApp:(GhostApp *)app {
    if ([app.status isEqualToString:@"TOMBSTONED"])
        return [NSString stringWithFormat:@"%@ — history only, try redownload", app.name];
    return [NSString stringWithFormat:@"%@ — tap to redownload", app.name];
}
- (void)openRedownloadForApp:(GhostApp *)app {
    if (!app.appleID.length) return;
    [[GhostCore shared] log:@"Redownload opened for %@ (%@) — Apple's controls from here", app.name, app.appleID];
    // ghostAdapter may be nil in Prefs context: fall back to direct open.
    if (ghostAdapter)
        [ghostAdapter openProductPageForAppleID:app.appleID];
    else {
        // Adapter already gates modern vs legacy openURL internally; mirror it.
        NSString *s = [NSString stringWithFormat:@"itms-apps://itunes.apple.com/app/id%@", app.appleID];
        NSURL *url = [NSURL URLWithString:s];
        UIApplication *ui = [UIApplication sharedApplication];
        if ([ui respondsToSelector:@selector(openURL:options:completionHandler:)])
            [ui openURL:url options:@{} completionHandler:nil];
        else {
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
            [ui openURL:url];
#pragma clang diagnostic pop
        }
    }
}
- (NSString *)summaryString {
    NSArray *all = [[GhostDB shared] allGhosts];
    NSUInteger tomb = 0;
    for (GhostApp *g in all)
        if ([g.status isEqualToString:@"TOMBSTONED"]) tomb++;
    return [NSString stringWithFormat:@"%lu owned, %lu tombstoned, %lu listed-elsewhere",
            (unsigned long)all.count, (unsigned long)tomb, (unsigned long)(all.count - tomb)];
}
@end
