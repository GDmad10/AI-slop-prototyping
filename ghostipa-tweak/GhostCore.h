// GhostCore.h — shared types: verdicts, settings keys, ghost record model (§7).
#import <Foundation/Foundation.h>

typedef NS_ENUM(NSInteger, GhostVerdict) {
    GhostVerdictUnknown = 0,        // not yet checked
    GhostVerdictRecordFound,        // GHOST RECORD FOUND — genuine Apple record
    GhostVerdictPackageAvailable,   // PACKAGE AVAILABLE — Apple's path permits install
    GhostVerdictInsufficient,       // "Insufficient evidence."
    GhostVerdictUnavailable,        // "Historical record found — download unavailable."
    GhostVerdictTombstoned          // receipt exists, Apple serves no metadata/package
};

@interface GhostApp : NSObject <NSSecureCoding>
@property (nonatomic, copy) NSString *appleID;      // adamID
@property (nonatomic, copy) NSString *bundleID;
@property (nonatomic, copy) NSString *name;
@property (nonatomic, copy) NSString *developer;
@property (nonatomic, copy) NSString *version;
@property (nonatomic, copy) NSString *storefront;   // country code of discovery
@property (nonatomic, copy) NSString *status;       // DELISTED / REGION_RESTRICTED / ...
@property (nonatomic, assign) BOOL metadataCached;
@property (nonatomic, copy) NSString *packageState; // AVAILABLE / UNAVAILABLE / UNKNOWN
@property (nonatomic, copy) NSString *source;       // "historical App Store record", etc.
@property (nonatomic, copy) NSString *iconURL;     // last-known artwork URL (may be dead now)
@property (nonatomic, copy) NSString *iconPath;    // on-device cached artwork (survives tombstoning)
@property (nonatomic, strong) NSDate *lastChecked;
@property (nonatomic, copy) NSDictionary *rawMetadata; // cached lookup payload (§10)
+ (instancetype)ghostWithAppleID:(NSString *)adamID raw:(NSDictionary *)raw storefront:(NSString *)cc;
@end

// Settings keys (Settings → Ghost IPA, §16).
static NSString *const kGhostEnabled      = @"GhostEnabled";
static NSString *const kGhostSearchHist   = @"GhostSearchHistorical";
static NSString *const kGhostShowDelisted = @"GhostShowDelisted";
static NSString *const kGhostShowRegion   = @"GhostShowRegionRestricted";
static NSString *const kGhostShowPurch    = @"GhostShowPreviousPurchases";
static NSString *const kGhostCacheMeta    = @"GhostCacheMetadata";
static NSString *const kGhostShowCompat   = @"GhostShowCompatibility";
static NSString *const kGhostExperimental = @"GhostExperimentalHooks";
static NSString *const kGhostDebugLog     = @"GhostDebugLog";
static NSString *const kGhostPreserveMode = @"GhostPreservationMode";

@interface GhostCore : NSObject
+ (instancetype)shared;
- (BOOL)boolForKey:(NSString *)key default:(BOOL)def;
- (void)log:(NSString *)format, ... NS_FORMAT_FUNCTION(1,2);
- (GhostVerdict)verdictForAppleID:(NSString *)adamID; // UNKNOWN until checked
- (void)setVerdict:(GhostVerdict)v forAppleID:(NSString *)adamID;
@end
