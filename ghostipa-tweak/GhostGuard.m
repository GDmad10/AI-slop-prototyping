// GhostGuard.m
#import "GhostGuard.h"

static NSString *const kCrashCount = @"GhostCrashCount";
static const NSInteger kCrashLimit = 2;

@implementation GhostGuard
// CFPreferences throughout (NSUserDefaults+suite is iOS 8+; this runs on 7).
+ (NSInteger)intForKey:(NSString *)key {
    CFPropertyListRef v = CFPreferencesCopyValue((__bridge CFStringRef)key,
        CFSTR("com.ghostipa.prefs"), kCFPreferencesAnyUser, kCFPreferencesAnyHost);
    NSInteger n = 0;
    if (v) {
        if (CFGetTypeID(v) == CFNumberGetTypeID()) n = [(__bridge NSNumber *)v integerValue];
        CFRelease(v);
    }
    return n;
}
+ (void)setInt:(NSInteger)n forKey:(NSString *)key {
    CFPreferencesSetValue((__bridge CFStringRef)key, (__bridge CFPropertyListRef)@(n),
        CFSTR("com.ghostipa.prefs"), kCFPreferencesAnyUser, kCFPreferencesAnyHost);
    CFPreferencesSynchronize(CFSTR("com.ghostipa.prefs"), kCFPreferencesAnyUser, kCFPreferencesAnyHost);
}
+ (void)installCrashGuard {
    static dispatch_once_t t;
    dispatch_once(&t, ^{
        NSSetUncaughtExceptionHandler(&GhostUncaught);
        [self setInt:[self intForKey:kCrashCount] + 1 forKey:kCrashCount];
        // Decremented on clean App Store termination via recordCleanExit.
    });
}
static void GhostUncaught(NSException *e) {
    NSLog(@"GhostIPA: crash captured (%@) — experimental hooks will be suppressed next launch", e.name);
}
+ (BOOL)experimentalHooksAllowed {
    return [self intForKey:kCrashCount] <= kCrashLimit;
}
+ (void)recordCleanExit {
    [self setInt:0 forKey:kCrashCount];
}
@end
