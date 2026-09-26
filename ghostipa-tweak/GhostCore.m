// GhostCore.m — prefs, debug console (§17), verdict cache.
#import "GhostCore.h"
#import "GhostGuard.h"

@implementation GhostApp
+ (BOOL)supportsSecureCoding { return YES; }
+ (instancetype)ghostWithAppleID:(NSString *)adamID raw:(NSDictionary *)raw storefront:(NSString *)cc {
    GhostApp *g = [[self alloc] init];
    g.appleID = adamID;
    g.bundleID = raw[@"bundleId"] ?: @"";
    g.name = raw[@"trackName"] ?: @"";
    g.developer = raw[@"artistName"] ?: @"";
    g.version = [raw[@"version"] description] ?: @"";
    g.storefront = cc ?: @"";
    g.status = @"DELISTED";
    g.metadataCached = YES;
    g.packageState = @"UNKNOWN";
    g.source = @"historical App Store record";
    g.iconURL = raw[@"artworkUrl512"] ?: raw[@"artworkUrl100"] ?: @"";
    g.iconPath = @"";
    g.lastChecked = [NSDate date];
    g.rawMetadata = raw;
    return g;
}
- (void)encodeWithCoder:(NSCoder *)c {
    for (NSString *k in @[@"appleID",@"bundleID",@"name",@"developer",@"version",
                          @"storefront",@"status",@"packageState",@"source",
                          @"iconURL",@"iconPath",@"lastChecked",@"rawMetadata"])
        [c encodeObject:[self valueForKey:k] forKey:k];
    [c encodeBool:self.metadataCached forKey:@"metadataCached"];
}
- (instancetype)initWithCoder:(NSCoder *)c {
    if ((self = [super init])) {
        // Class-specific decodes under secure coding (iOS 11+ writer); legacy
        // decodes on iOS 8–10 where the archive was written without it.
        NSArray *strKeys = @[@"appleID",@"bundleID",@"name",@"developer",@"version",
                             @"storefront",@"status",@"packageState",@"source",
                             @"iconURL",@"iconPath"];
        if ([c respondsToSelector:@selector(decodeObjectOfClass:forKey:)]) {
            for (NSString *k in strKeys)
                [self setValue:[c decodeObjectOfClass:[NSString class] forKey:k] forKey:k];
            _lastChecked = [c decodeObjectOfClass:[NSDate class] forKey:@"lastChecked"];
            NSSet *rawCls = [NSSet setWithObjects:[NSDictionary class],[NSArray class],
                             [NSString class],[NSNumber class],nil];
            _rawMetadata = [c decodeObjectOfClasses:rawCls forKey:@"rawMetadata"];
        } else {
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
            for (NSString *k in [strKeys arrayByAddingObjectsFromArray:@[@"lastChecked",@"rawMetadata"]])
                [self setValue:[c decodeObjectForKey:k] forKey:k];
#pragma clang diagnostic pop
        }
        _metadataCached = [c decodeBoolForKey:@"metadataCached"];
    }
    return self;
}
@end

@implementation GhostCore {
    NSMutableDictionary<NSString *, NSNumber *> *_verdicts;
}
+ (instancetype)shared {
    static GhostCore *s; static dispatch_once_t t;
    dispatch_once(&t, ^{ s = [[self alloc] init]; });
    return s;
}
- (instancetype)init {
    if ((self = [super init])) {
        _verdicts = [NSMutableDictionary dictionary];
        [GhostGuard installCrashGuard]; // fail-safe (§20)
    }
    return self;
}
- (BOOL)boolForKey:(NSString *)key default:(BOOL)def {
    // CFPreferences, not NSUserDefaults+suite (initWithSuiteName: is iOS 8+).
    // App-ID domain is shared across the AppStore, Preferences and TestFlight
    // host processes on every version from 7.0 up.
    CFPropertyListRef v = CFPreferencesCopyValue((__bridge CFStringRef)key,
        CFSTR("com.ghostipa.prefs"), kCFPreferencesAnyUser, kCFPreferencesAnyHost);
    if (!v) return def;
    BOOL b = YES;
    if (CFGetTypeID(v) == CFBooleanGetTypeID()) b = CFBooleanGetValue((CFBooleanRef)v);
    else if (CFGetTypeID(v) == CFNumberGetTypeID()) b = [(__bridge NSNumber *)v boolValue];
    CFRelease(v);
    return b;
}
}
- (void)log:(NSString *)format, ... {
    if (![self boolForKey:kGhostDebugLog default:NO]) return;
    va_list ap; va_start(ap, format);
    NSString *msg = [[NSString alloc] initWithFormat:format arguments:ap];
    va_end(ap);
    NSLog(@"GhostIPA: %@", msg); // §17 debug console via oslog/syslog
}
- (GhostVerdict)verdictForAppleID:(NSString *)adamID {
    NSNumber *v = _verdicts[adamID];
    if (v) return (GhostVerdict)v.integerValue;
    return GhostVerdictUnknown;
}
- (void)setVerdict:(GhostVerdict)v forAppleID:(NSString *)adamID {
    _verdicts[adamID] = @(v);
}
@end
