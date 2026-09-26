// GhostBadge.m — frame-based layout (iOS 8 safe: no layout anchors anywhere).
#import "GhostBadge.h"
#import "GhostCore.h"
#import "GhostCompat.h"
#import <objc/runtime.h>

static const void *kGhostBadgeKey = &kGhostBadgeKey;

@implementation GhostBadge
+ (NSString *)ghostBundlePath {
    return @"/Library/MobileSubstrate/DynamicLibraries/GhostIPA.bundle";
}
+ (UIImage *)ghostImage {
    // @2x/@3x handled by UIImage named-lookup inside the bundle.
    NSString *p = [[self ghostBundlePath] stringByAppendingPathComponent:@"ghost.png"];
    UIImage *img = [UIImage imageWithContentsOfFile:p];
    if (!img) {
        // Prefs-bundle fallback (settings icon) so *something* marks the row.
        NSString *fb = @"/Library/PreferenceBundles/GhostIPAPrefs.bundle/icon.png";
        img = [UIImage imageWithContentsOfFile:fb];
    }
    return img; // nil until art is dropped in — callers fall back to text
}
+ (UIImage *)tfImage {
    NSString *p = [[self ghostBundlePath] stringByAppendingPathComponent:@"testflight.png"];
    return [UIImage imageWithContentsOfFile:p]; // nil until maintainer art lands
}
+ (UIImageView *)ghostImageViewWithSize:(CGFloat)pt {
    UIImage *img = [self ghostImage];
    if (!img) return nil;
    UIImageView *iv = [[UIImageView alloc] initWithImage:img];
    iv.frame = CGRectMake(0, 0, pt, pt);
    iv.contentMode = UIViewContentModeScaleAspectFit;
    iv.accessibilityLabel = @"Ghost app";
    return iv;
}
+ (UIImage *)artworkForApp:(GhostApp *)app {
    if (app.iconPath.length) {
        UIImage *cached = [UIImage imageWithContentsOfFile:app.iconPath];
        if (cached) return cached;
    }
    return [self ghostImage]; // ghost mark (or nil → text-only, never a grey box)
}
+ (NSString *)tombstoneCardForApp:(GhostApp *)app {
    NSMutableString *m = [NSMutableString stringWithFormat:
        @"Ghost App — TOMBSTONED\n%@\nDeveloper: %@\n\n"
        @"Apple no longer serves metadata or a package for this record, but your "
        @"purchase history proves it existed. Everything below is preserved from "
        @"earlier captures.\n\nHistorical version:\n%@\nBundle:\n%@\nApple ID:\n%@",
        app.name, app.developer,
        app.version.length ? app.version : @"unknown",
        app.bundleID.length ? app.bundleID : @"unknown",
        app.appleID];
    return m;
}
+ (void)applyRowArtwork:(UIView *)artworkView {
    // Overlays the ghost mark top-right of the row's artwork; no-ops without art.
    UIImage *img = [self ghostImage];
    if (!img || !artworkView) return;
    // Remove a previous stamp (cell reuse) before stamping again.
    for (UIView *sub in artworkView.subviews)
        if (sub.tag == 0x6A05A) [sub removeFromSuperview];
    CGFloat s = MIN(artworkView.bounds.size.width, artworkView.bounds.size.height) * 0.42;
    if (s < 1) s = 22;
    UIImageView *iv = [[UIImageView alloc] initWithImage:img];
    iv.tag = 0x6A05A;
    iv.contentMode = UIViewContentModeScaleAspectFit;
    // Frame-based so iOS 8 can run it; sticks to top-right on resize.
    iv.frame = CGRectMake(artworkView.bounds.size.width - s - 2, 2, s, s);
    iv.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin | UIViewAutoresizingFlexibleBottomMargin;
    [artworkView addSubview:iv];
}
+ (NSAttributedString *)ghostSubtitleForApp:(GhostApp *)app {
    // When art is present the row shows the ghost mark; keep the emoji prefix
    // only as the no-art fallback so rows never look unmarked.
    NSString *prefix = ([self ghostImage] ? @"Ghost App" : @"👻 Ghost App");
    NSString *s = [NSString stringWithFormat:@"%@ — %@ • %@", prefix, app.developer ?: @"", app.status ?: @"DELISTED"];
    return [[NSAttributedString alloc] initWithString:s
                                          attributes:@{NSForegroundColorAttributeName: [UIColor systemOrangeColor],
                                                       NSFontAttributeName: [UIFont systemFontOfSize:12]}];
}
+ (NSString *)statusCardForApp:(GhostApp *)app showCompat:(BOOL)showCompat {
    NSMutableString *m = [NSMutableString stringWithFormat:
        @"👻 Ghost App\n%@\nDeveloper: %@\nStatus:\n%@\nHistorical version:\n%@\nDistribution:\n%@",
        app.name, app.developer, app.status,
        app.version.length ? app.version : @"unknown",
        [app.packageState isEqualToString:@"AVAILABLE"] ? @"Get (normal App Store control)"
                                                       : @"Unavailable"];
    if (showCompat) {
        NSString *minOS = app.rawMetadata[@"minimumOsVersion"] ?: @"unknown";
        [m appendFormat:@"\nCompatibility:\n%@+", minOS];
    }
    if ([app.packageState isEqualToString:@"AVAILABLE"])
        [m appendString:@"\n\nUse the normal App Store Get control above."];
    else
        [m appendString:@"\n\nGhost record found, but Apple is not currently providing "
                        "an authorized download for this application."];
    return m;
}
+ (UILabel *)attachToProductView:(UIView *)page app:(GhostApp *)app installable:(BOOL)installable {
    // Once-guard: PDPs re-layout on scroll/tab switches — badge exactly once.
    if ([objc_getAssociatedObject(page, kGhostBadgeKey) boolValue]) return nil;
    objc_setAssociatedObject(page, kGhostBadgeKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    UILabel *lab = [[UILabel alloc] init];
    lab.numberOfLines = 0;
    BOOL tomb = [app.status isEqualToString:@"TOMBSTONED"];
    if (tomb)
        lab.text = [self tombstoneCardForApp:app];
    else
        lab.text = [self statusCardForApp:app showCompat:[[GhostCore shared] boolForKey:kGhostShowCompat default:YES]];
    lab.font = [UIFont systemFontOfSize:13];
    lab.textColor = GhostSecondaryLabelColor();
    CGFloat y = 8, w = page.bounds.size.width - 32;
    if (w < 50) w = 50; // page not laid out yet — hook site re-calls after layout
    UIImage *head = tomb ? [self artworkForApp:app] : [self ghostImage];
    UIImageView *ghost = nil;
    if (head) {
        ghost = [[UIImageView alloc] initWithImage:head];
        ghost.frame = CGRectMake(0, 0, 44, 44);
        ghost.contentMode = UIViewContentModeScaleAspectFit;
    }
    if (ghost) {
        ghost.frame = CGRectMake(16, y, 44, 44);
        ghost.autoresizingMask = UIViewAutoresizingFlexibleRightMargin | UIViewAutoresizingFlexibleBottomMargin;
        [page addSubview:ghost];
        y += 52;
    }
    CGSize fit = [lab sizeThatFits:CGSizeMake(w, CGFLOAT_MAX)];
    lab.frame = CGRectMake(16, y, w, fit.height);
    lab.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [page addSubview:lab];
    [[GhostCore shared] log:@"UI injection = %@ (%@)", installable ? @"SUCCESS + Get control" : @"SUCCESS (record only)", app.appleID];
    return lab;
}
@end
