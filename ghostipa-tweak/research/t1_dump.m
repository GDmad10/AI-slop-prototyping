// t1_dump.m — runtime ObjC class lister. No private API: uses only
// objc_getClassList + class_getName (public libobjc). Injects via
// DYLD_INSERT_LIBRARIES into AppStore, or runs standalone listing all classes.
// Build (on macOS builder): clang -framework Foundation t1_dump.m -o t1_dump
#import <Foundation/Foundation.h>
#import <objc/runtime.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        NSString *pat = @"(Search|ProductLockup|ProductPage|Storefront|PurchaseHistory|Availability|DownloadManager|LookupRequest)";
        NSRegularExpression *re = [NSRegularExpression regularExpressionWithPattern:pat options:NSRegularExpressionCaseInsensitive error:nil];
        int n = objc_getClassList(NULL, 0);
        Class *cls = malloc(sizeof(Class) * n);
        n = objc_getClassList(cls, n);
        NSMutableArray *hits = [NSMutableArray array];
        for (int i = 0; i < n; i++) {
            NSString *name = NSStringFromClass(cls[i]);
            if ([re numberOfMatchesInString:name options:0 range:NSMakeRange(0, name.length)])
                [hits addObject:name];
        }
        free(cls);
        [hits sortUsingSelector:@selector(compare:)];
        NSString *out = [@"/var/mobile/Library/GhostIPA/T1-classes.txt" stringByExpandingTildeInPath];
        NSString *txt = [NSString stringWithFormat:@"=== T1-runtime %@ ===\n%@\n",
                         [[NSProcessInfo processInfo] operatingSystemVersionString],
                         [hits componentsJoinedByString:@"\n"]];
        [txt writeToFile:out atomically:YES encoding:NSUTF8StringEncoding error:nil];
        NSLog(@"GhostIPA-T1: %lu classes -> %@", (unsigned long)hits.count, out);
        for (NSString *h in hits) NSLog(@"GhostIPA-T1: %@", h);
    }
    return 0;
}
