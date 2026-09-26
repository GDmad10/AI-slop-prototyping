// GhostDB.h — local store /var/mobile/Library/GhostIPA/apps.sqlite (§7) + JSON export (§15).
#import <Foundation/Foundation.h>
@class GhostApp;

@interface GhostDB : NSObject
+ (instancetype)shared;
- (void)saveGhost:(GhostApp *)app;
- (void)markTombstoned:(NSString *)adamID; // receipt lives, Apple serves nothing — keep cache
- (NSString *)cacheArtworkForApp:(GhostApp *)app; // downloads iconURL → Archive/<id>/icon.png
- (GhostApp *)ghostForAppleID:(NSString *)adamID;
- (NSArray<GhostApp *> *)allGhosts;          // GHOST APPLICATIONS list (§22)
- (NSArray<GhostApp *> *)ghostsMatching:(NSString *)query; // name/bundle/developer/adamID
- (void)clearCache;                          // [ Clear Ghost Cache ]
- (BOOL)exportJSONToPath:(NSString *)path error:(NSError **)err; // GhostApps.json (§15)
- (BOOL)importJSONFromPath:(NSString *)path error:(NSError **)err;
@end
