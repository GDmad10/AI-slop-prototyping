// GhostCompat.h — iOS 7 backport shims. Every API newer than 7.0 used by the
// tweak funnels through here with a runtime gate. Minimum deployment: iOS 7.0
// (32-bit armv7/armv7s included — no 64-bit-only calls, ever).
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

static inline NSInteger GhostSystemMajorVersion(void) {
    // NSProcessInfo.operatingSystemVersion is iOS 8+; UIDevice works on 7.
    NSString *v = [[UIDevice currentDevice] systemVersion];
    return [[v componentsSeparatedByString:@"."][0] integerValue];
}

static inline UIColor *GhostSecondaryLabelColor(void) {
    // secondaryLabelColor is iOS 13+. Gray reads the same on iOS 8–12.
    if ([UIColor respondsToSelector:@selector(secondaryLabelColor)])
        return [UIColor secondaryLabelColor];
    return [UIColor grayColor];
}

static inline NSString *GhostEncodeURLQuery(NSString *s) {
    // stringByAddingPercentEncodingWithAllowedCharacters is iOS 9+.
    if ([s respondsToSelector:@selector(stringByAddingPercentEncodingWithAllowedCharacters:)])
        return [s stringByAddingPercentEncodingWithAllowedCharacters:[NSCharacterSet URLQueryAllowedCharacterSet]];
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    return [s stringByAddingPercentEscapesUsingEncoding:NSUTF8StringEncoding];
#pragma clang diagnostic pop
}

static inline NSData *GhostArchive(id obj) {
    // requiringSecureCoding variant is iOS 11+.
    if ([NSKeyedArchiver respondsToSelector:@selector(archivedDataWithRootObject:requiringSecureCoding:error:)]) {
        NSError *err = nil;
        NSData *d = [NSKeyedArchiver archivedDataWithRootObject:obj requiringSecureCoding:YES error:&err];
        if (d) return d;
    }
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    return [NSKeyedArchiver archivedDataWithRootObject:obj];
#pragma clang diagnostic pop
}

static inline id GhostUnarchive(NSData *d, NSSet *classes) {
    // unarchivedObjectOfClasses:fromData:error: is iOS 11+.
    if ([NSKeyedUnarchiver respondsToSelector:@selector(unarchivedObjectOfClasses:fromData:error:)]) {
        NSError *err = nil;
        id o = [NSKeyedUnarchiver unarchivedObjectOfClasses:classes fromData:d error:&err];
        if (o) return o;
    }
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    @try { return [NSKeyedUnarchiver unarchiveObjectWithData:d]; }
    @catch (NSException *e) { return nil; }
#pragma clang diagnostic pop
}
