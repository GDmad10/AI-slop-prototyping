// GhostPrefs.m — Settings → Ghost IPA (§16) + GHOST APPLICATIONS list (§22).
#import <Preferences/PSListController.h>
#import <Preferences/PSSpecifier.h>

@interface GhostPrefsController : PSListController
@end

@implementation GhostPrefsController
- (NSArray *)specifiers {
    if (!_specifiers) {
        NSMutableArray *s = [NSMutableArray array];
        NSArray *toggles = @[
            @[@"GhostEnabled", @"Enable Ghost Apps", @YES],
            @[@"GhostSearchHistorical", @"Search historical records", @YES],
            @[@"GhostShowDelisted", @"Show delisted apps", @YES],
            @[@"GhostShowRegionRestricted", @"Show region-restricted records", @YES],
            @[@"GhostShowPreviousPurchases", @"Show previous-purchase records", @YES],
            @[@"GhostCacheMetadata", @"Cache metadata", @YES],
            @[@"GhostShowCompatibility", @"Show compatibility information", @YES],
            @[@"GhostPreservationMode", @"Preservation Mode", @NO],
            @[@"GhostExperimentalHooks", @"Experimental App Store hooks", @NO],
            @[@"GhostDebugLog", @"Debug logging", @NO],
        ];
        for (NSArray *t in toggles) {
            PSSpecifier *sp = [PSSpecifier preferenceSpecifierNamed:t[1]
                target:self set:@selector(setPreferenceValue:specifier:)
                get:@selector(readPreferenceValue:) detail:nil cell:PSSwitchCell edit:nil];
            [sp setProperty:t[0] forKey:@"key"];
            [sp setProperty:@"com.ghostipa.prefs" forKey:@"defaults"];
            [sp setProperty:t[2] forKey:@"default"];
            [s addObject:sp];
        }
        PSSpecifier *clear = [PSSpecifier preferenceSpecifierNamed:@"Clear Ghost Cache"
            target:self set:nil get:nil detail:nil cell:PSButtonCell edit:nil];
        clear.buttonAction = @selector(clearCache);
        [s addObject:clear];
        PSSpecifier *list = [PSSpecifier preferenceSpecifierNamed:@"GHOST APPLICATIONS"
            target:self set:nil get:nil detail:nil cell:PSGroupCell edit:nil];
        [s addObject:list];
        // Recently discovered ghosts, rendered from the tweak's JSON sidecar
        // (/var/mobile/Library/GhostIPA/ghosts.json) — no tweak classes needed.
        NSData *j = [NSData dataWithContentsOfFile:@"/var/mobile/Library/GhostIPA/ghosts.json"];
        NSArray *ghosts = j ? [NSJSONSerialization JSONObjectWithData:j options:0 error:nil] : nil;
        if ([ghosts isKindOfClass:[NSArray class]] && ghosts.count) {
            for (NSDictionary *g in ghosts) {
                NSString *title = [NSString stringWithFormat:@"👻 %@ (%@)",
                                   g[@"name"] ?: @"?", g[@"status"] ?: @"?"];
                PSSpecifier *row = [PSSpecifier preferenceSpecifierNamed:title
                    target:self set:nil get:@selector(ghostDetail:) detail:nil cell:PSStaticTextCell edit:nil];
                [row setProperty:g[@"apple_id"] forKey:@"ghostAppleID"];
                [s addObject:row];
            }
        } else {
            PSSpecifier *empty = [PSSpecifier preferenceSpecifierNamed:@"No ghosts discovered yet — search the App Store."
                target:self set:nil get:nil detail:nil cell:PSStaticTextCell edit:nil];
            [s addObject:empty];
        }
        _specifiers = s;
    }
    return _specifiers;
}
- (NSString *)ghostDetail:(PSSpecifier *)spec {
    return [spec propertyForKey:@"ghostAppleID"] ?: @"";
}
- (void)clearCache {
    [[NSFileManager defaultManager] removeItemAtPath:@"/var/mobile/Library/GhostIPA/apps.archive" error:nil];
    [[NSFileManager defaultManager] removeItemAtPath:@"/var/mobile/Library/GhostIPA/ghosts.json" error:nil];
    [self reloadSpecifiers]; // empty-state row re-renders immediately
}
@end
