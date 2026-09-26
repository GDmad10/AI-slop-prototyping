// GhostBadge.h — ghost indicator art + status block for the normal PDP/row (§9).
#import <UIKit/UIKit.h>
@class GhostApp;

@interface GhostBadge : NSObject
// Ghost art from GhostIPA.bundle (ghost[@2x,@3x].png). Nil until the
// maintainer drops the file in — every caller must nil-check (text fallback).
+ (UIImage *)ghostImage;
// TestFlight mark from GhostIPA.bundle (testflight[@2x,@3x].png, maintainer art).
// Nil until supplied — callers fall back to +ghostImage, then text.
+ (UIImage *)tfImage;
// Sized image view for PDP header / status card. Nil image → nil view.
+ (UIImageView *)ghostImageViewWithSize:(CGFloat)pt;
// App artwork: on-device cache first (survives tombstoning), then ghost mark.
// Never returns Apple's dead URL — the grey box is exactly what this kills.
+ (UIImage *)artworkForApp:(GhostApp *)app;
+ (NSString *)tombstoneCardForApp:(GhostApp *)app;
// Stamp ghost art onto a search row's artwork view; keeps Apple's image if absent.
+ (void)applyRowArtwork:(UIView *)artworkView;
// Attributed "Ghost App" subtitle for search rows (emoji prefix only as fallback).
+ (NSAttributedString *)ghostSubtitleForApp:(GhostApp *)app;
// Full status card text for the product page.
+ (NSString *)statusCardForApp:(GhostApp *)app showCompat:(BOOL)showCompat;
// Badge a normal product-page view: adds subtitle label, returns it.
+ (UILabel *)attachToProductView:(UIView *)page app:(GhostApp *)app installable:(BOOL)installable;
@end
