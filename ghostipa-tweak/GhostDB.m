// GhostDB.m — NSSecureCoding archive store (no sqlite dep; same schema as §7).
#import "GhostDB.h"
#import "GhostCore.h"
#import "GhostCompat.h"

@implementation GhostDB {
    NSMutableDictionary<NSString *, GhostApp *> *_apps;
    NSString *_storePath;
    NSString *_archiveDir;
}
+ (instancetype)shared {
    static GhostDB *s; static dispatch_once_t t;
    dispatch_once(&t, ^{ s = [[self alloc] init]; });
    return s;
}
- (instancetype)init {
    if ((self = [super init])) {
        NSString *base = @"/var/mobile/Library/GhostIPA";
        _storePath = [base stringByAppendingPathComponent:@"apps.archive"];
        _archiveDir = [base stringByAppendingPathComponent:@"Archive"];
        [[NSFileManager defaultManager] createDirectoryAtPath:base withIntermediateDirectories:YES attributes:nil error:nil];
        [[NSFileManager defaultManager] createDirectoryAtPath:_archiveDir withIntermediateDirectories:YES attributes:nil error:nil];
        NSData *d = [NSData dataWithContentsOfFile:_storePath];
        if (d) {
            NSSet *cls = [NSSet setWithObjects:[NSDictionary class],[NSArray class],[GhostApp class],[NSString class],[NSDate class],[NSNumber class],nil];
            _apps = [GhostUnarchive(d, cls) mutableCopy];
        }
        if (!_apps) _apps = [NSMutableDictionary dictionary];
    }
    return self;
}
- (void)_flush {
    NSData *d = GhostArchive(_apps);
    [d writeToFile:_storePath atomically:YES];
    // Sidecar for the Settings bundle (§22): plain JSON it can read without
    // linking the tweak's classes.
    NSMutableArray *sidecar = [NSMutableArray array];
    for (GhostApp *g in [self allGhosts])
        [sidecar addObject:@{@"name": g.name ?: @"", @"apple_id": g.appleID ?: @"",
                             @"bundle_id": g.bundleID ?: @"", @"developer": g.developer ?: @"",
                             @"status": g.status ?: @"", @"version": g.version ?: @""}];
    NSData *j = [NSJSONSerialization dataWithJSONObject:sidecar options:0 error:nil];
    [j writeToFile:[@"/var/mobile/Library/GhostIPA/ghosts.json"] atomically:YES];
}
- (void)saveGhost:(GhostApp *)app {
    if (!app.appleID.length) return;
    _apps[app.appleID] = app;
    [self _flush];
    // Preservation Mode (§21): per-app archive dir.
    if ([[GhostCore shared] boolForKey:kGhostPreserveMode default:NO] && app.rawMetadata) {
        NSString *dir = [_archiveDir stringByAppendingPathComponent:app.appleID];
        [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
        NSData *meta = [NSJSONSerialization dataWithJSONObject:app.rawMetadata options:NSJSONWritingPrettyPrinted error:nil];
        [meta writeToFile:[dir stringByAppendingPathComponent:@"metadata.json"] atomically:YES];
        NSDictionary *hist = @{@"apple_id": app.appleID, @"bundle_id": app.bundleID ?: @"",
                               @"status": app.status ?: @"", @"package": app.packageState ?: @"UNKNOWN"};
        NSData *h = [NSJSONSerialization dataWithJSONObject:hist options:NSJSONWritingPrettyPrinted error:nil];
        [h writeToFile:[dir stringByAppendingPathComponent:@"history.json"] atomically:YES];
    }
    [[GhostCore shared] log:@"DB saved %@ (%@)", app.name, app.appleID];
    // Artwork is cached on EVERY save, not just Preservation Mode: if Apple
    // tombstones the record later (grey box), the cached icon keeps the card alive.
    if ([[GhostCore shared] boolForKey:kGhostCacheMeta default:YES])
        [self cacheArtworkForApp:app];
}
- (NSString *)cacheArtworkForApp:(GhostApp *)app {
    if (!app.appleID.length) return nil;
    NSString *dir = [_archiveDir stringByAppendingPathComponent:app.appleID];
    NSString *dest = [dir stringByAppendingPathComponent:@"icon.png"];
    if ([[NSFileManager defaultManager] fileExistsAtPath:dest]) {
        app.iconPath = dest;
        return dest;
    }
    if (!app.iconURL.length) return app.iconPath.length ? app.iconPath : nil;
    NSData *d = [NSData dataWithContentsOfURL:[NSURL URLWithString:app.iconURL]];
    if (!d.length) return app.iconPath.length ? app.iconPath : nil; // URL dead — keep old cache
    [[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
    if ([d writeToFile:dest atomically:YES]) app.iconPath = dest;
    [self _flush]; // persist iconPath
    return app.iconPath;
}
- (void)markTombstoned:(NSString *)adamID {
    GhostApp *g = _apps[adamID];
    if (!g) return;
    g.status = @"TOMBSTONED";
    g.packageState = @"UNAVAILABLE";
    g.lastChecked = [NSDate date];
    [self _flush];
    [[GhostCore shared] setVerdict:GhostVerdictTombstoned forAppleID:adamID];
    [[GhostCore shared] log:@"TOMBSTONED %@ — receipt lives, Apple serves nothing; cache kept", adamID];
}
- (GhostApp *)ghostForAppleID:(NSString *)adamID { return _apps[adamID]; }
- (NSArray<GhostApp *> *)allGhosts {
    return [_apps.allValues sortedByDescriptors:@[[NSSortDescriptor sortDescriptorWithKey:@"name" ascending:YES]]];
}
- (NSArray<GhostApp *> *)ghostsMatching:(NSString *)query {
    if (!query.length) return @[];
    NSString *q = query.lowercaseString;
    NSMutableArray *out = [NSMutableArray array];
    for (GhostApp *g in _apps.allValues) {
        // rangeOfString:, not containsString: (iOS 8+) — floor is 7.0.
        if ([g.name.lowercaseString rangeOfString:q].location != NSNotFound ||
            [g.bundleID.lowercaseString rangeOfString:q].location != NSNotFound ||
            [g.developer.lowercaseString rangeOfString:q].location != NSNotFound ||
            [g.appleID rangeOfString:q].location != NSNotFound)
            [out addObject:g];
    }
    return out;
}
- (void)clearCache { [_apps removeAllObjects]; [self _flush]; }
- (BOOL)exportJSONToPath:(NSString *)path error:(NSError **)err {
    NSMutableArray *arr = [NSMutableArray array];
    for (GhostApp *g in _apps.allValues)
        [arr addObject:@{@"name": g.name ?: @"", @"apple_id": g.appleID ?: @"",
                         @"bundle_id": g.bundleID ?: @"", @"developer": g.developer ?: @"",
                         @"last_known_version": g.version ?: @"",
                         @"source": g.source ?: @"historical App Store record"}];
    NSData *d = [NSJSONSerialization dataWithJSONObject:arr options:NSJSONWritingPrettyPrinted error:err];
    return d ? [d writeToFile:path options:NSDataWritingAtomic error:err] : NO;
}
- (BOOL)importJSONFromPath:(NSString *)path error:(NSError **)err {
    NSData *d = [NSData dataWithContentsOfFile:path options:0 error:err];
    if (!d) return NO;
    NSArray *arr = [NSJSONSerialization JSONObjectWithData:d options:0 error:err];
    if (![arr isKindOfClass:[NSArray class]]) return NO;
    for (NSDictionary *e in arr) {
        GhostApp *g = [[GhostApp alloc] init];
        g.appleID = [e[@"apple_id"] description]; g.name = e[@"name"];
        g.bundleID = e[@"bundle_id"]; g.developer = e[@"developer"];
        g.version = e[@"last_known_version"]; g.source = e[@"source"];
        g.lastChecked = [NSDate date]; g.status = @"DELISTED"; g.packageState = @"UNKNOWN";
        if (g.appleID.length) _apps[g.appleID] = g;
    }
    [self _flush];
    return YES;
}
@end
