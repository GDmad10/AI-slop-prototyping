// GhostScan.m — genuine-record-only discovery. No fabrication (§20).
#import "GhostScan.h"
#import "GhostCore.h"
#import "GhostDB.h"
#import "GhostCompat.h"

// Storefronts swept for metadata (§14). Account region never changed.
static NSArray<NSString *> *GhostStorefronts(void) {
    return @[@"us",@"gb",@"dk",@"jp",@"ru",@"de",@"fr",@"es",@"kr",@"cn"];
}

@implementation GhostScan
+ (instancetype)shared {
    static GhostScan *s; static dispatch_once_t t;
    dispatch_once(&t, ^{ s = [[self alloc] init]; });
    return s;
}

- (GhostApp *)resolveGhostURL:(NSURL *)url {
    if (![[url.scheme lowercaseString] isEqualToString:@"ghost"]) return nil;
    GhostCore *core = [GhostCore shared];
    if ([url.host isEqualToString:@"app"]) {
        NSString *adamID = url.pathComponents.count > 1 ? url.pathComponents[1] : nil;
        if (!adamID.length) return nil;
        GhostApp *cached = [[GhostDB shared] ghostForAppleID:adamID];
        if (cached) return cached;
        NSDictionary *raw = [self lookupAdamID:adamID country:@"us"];
        if (!raw) return nil; // no genuine record → no ghost (§20)
        GhostApp *g = [GhostApp ghostWithAppleID:adamID raw:raw storefront:@"us"];
        [[GhostDB shared] saveGhost:g];
        [[GhostCore shared] setVerdict:GhostVerdictRecordFound forAppleID:adamID];
        [core log:@"GhostURL resolved app/%@ → %@", adamID, g.name];
        return g;
    }
    if ([url.host isEqualToString:@"bundle"]) {
        NSString *bundle = [url.path stringByTrimmingCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@"/"]];
        NSArray *hits = [[GhostDB shared] ghostsMatching:bundle];
        if (hits.count) return hits.firstObject;
        [core log:@"GhostURL bundle/%@ has no cached record — needs search evidence", bundle];
        return nil; // bundle alone proves nothing without a lookup hit
    }
    return nil;
}

- (NSDictionary *)lookupAdamID:(NSString *)adamID country:(NSString *)cc {
    NSString *qs = [NSString stringWithFormat:@"https://itunes.apple.com/lookup?id=%@&country=%@&entity=software",
                    adamID, cc ?: @"us"];
    NSData *d = [NSData dataWithContentsOfURL:[NSURL URLWithString:qs]];
    if (!d) return nil;
    NSDictionary *j = [NSJSONSerialization JSONObjectWithData:d options:0 error:nil];
    NSArray *r = j[@"results"];
    return [r isKindOfClass:[NSArray class]] && r.count ? r.firstObject : nil;
}

- (NSArray *)searchTerm:(NSString *)term country:(NSString *)cc {
    NSString *e = GhostEncodeURLQuery(term);
    NSString *qs = [NSString stringWithFormat:@"https://itunes.apple.com/search?term=%@&country=%@&entity=software&limit=50", e, cc];
    NSData *d = [NSData dataWithContentsOfURL:[NSURL URLWithString:qs]];
    if (!d) return @[];
    NSDictionary *j = [NSJSONSerialization JSONObjectWithData:d options:0 error:nil];
    NSArray *r = j[@"results"];
    return [r isKindOfClass:[NSArray class]] ? r : @[];
}

- (void)scanQuery:(NSString *)query visibleAppleIDs:(NSSet<NSString *> *)visible completion:(GhostScanDone)done {
    GhostCore *core = [GhostCore shared];
    if (![core boolForKey:kGhostEnabled default:YES] || ![core boolForKey:kGhostSearchHist default:YES]) {
        if (done) done(@[]); return;
    }
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        [core log:@"Search = \"%@\"", query];
        [core log:@"Normal results = %lu", (unsigned long)visible.count];
        NSMutableDictionary<NSString *, GhostApp *> *found = [NSMutableDictionary dictionary];
        // Pass 1: cached ghosts matching the query (offline DB, §15/§22 list).
        // Each cached match is revalidated live: a lookup that now returns
        // nothing means Apple tombstoned it — mark, keep cache, still display.
        for (GhostApp *g in [[GhostDB shared] ghostsMatching:query]) {
            if ([visible containsObject:g.appleID]) continue;
            NSDictionary *re = [self lookupAdamID:g.appleID country:@"us"];
            if (!re) {
                [[GhostDB shared] markTombstoned:g.appleID];
                [core log:@"Tombstone confirmed in Purchased flow: %@ — showing cached card", g.appleID];
            } else {
                g.lastChecked = [NSDate date];
            }
            found[g.appleID] = g;
        }
        // Pass 2: alternate-storefront sweep — records visible elsewhere but not here (§14).
        // Concurrent with a bounded worker count: 9 sequential lookups would stall
        // results by ~10-60s; parallel keeps the whole sweep near single-lookup latency.
        NSArray<NSString *> *ccs = GhostStorefronts();
        dispatch_apply(ccs.count, dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^(size_t idx) {
            NSString *cc = ccs[idx];
            if ([cc isEqualToString:@"us"]) return; // primary storefront already shown
            for (NSDictionary *raw in [self searchTerm:query country:cc]) {
                NSString *adamID = [raw[@"trackId"] description];
                @synchronized (found) {
                    if (!adamID.length || [visible containsObject:adamID] || found[adamID]) continue;
                }
                // Confirm the record is genuine by re-looking it up directly.
                NSDictionary *confirm = [self lookupAdamID:adamID country:cc];
                if (!confirm) continue;
                GhostApp *g = [GhostApp ghostWithAppleID:adamID raw:confirm storefront:cc];
                g.status = @"REGION_RESTRICTED";
                if (![core boolForKey:kGhostShowRegion default:YES]) continue;
                if ([core boolForKey:kGhostCacheMeta default:YES]) [[GhostDB shared] saveGhost:g];
                [[GhostCore shared] setVerdict:GhostVerdictRecordFound forAppleID:adamID];
                @synchronized (found) { found[adamID] = g; }
                [core log:@"Ghost record found: Apple ID = %@ (%@, %@)", adamID, g.name, cc];
            }
        });
        NSArray *ghosts = found.allValues;
        [core log:@"Historical records queried = %lu", (unsigned long)(1 + GhostStorefronts().count - 1)];
        [core log:@"Metadata = %@ / Distribution = %@",
         ghosts.count ? @"FOUND" : @"NOT FOUND",
         @"UNAVAILABLE (until App Store serves a Get control)"];
        dispatch_async(dispatch_get_main_queue(), ^{ if (done) done(ghosts); });
    });
}
@end
