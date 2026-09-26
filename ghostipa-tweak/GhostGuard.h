// GhostGuard.h — fail-safe: consecutive-crash counter auto-disables experimental hooks (§20).
#import <Foundation/Foundation.h>

@interface GhostGuard : NSObject
+ (void)installCrashGuard;
+ (BOOL)experimentalHooksAllowed; // NO after 2 consecutive App Store crashes
+ (void)recordCleanExit;
@end
