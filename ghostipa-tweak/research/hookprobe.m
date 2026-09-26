// hookprobe.m — throwaway method logger. Confirms the EXACT selector that
// delivers search results on the target iOS BEFORE Ghost wires its real hook.
// Inject with DYLD_INSERT_LIBRARIES into AppStore, perform one search, read syslog.
// Uses only public objc runtime — no private headers needed.
//
// Build: clang -dynamiclib -framework Foundation hookprobe.m -o hookprobe.dylib
// Run:   DYLD_INSERT_LIBRARIES=/path/hookprobe.dylib /Applications/AppStore.app/AppStore
// Read:  log stream | grep GhostProbe
#import <Foundation/Foundation.h>
#import <objc/runtime.h>

// After T1 gives class names, fill these in and rebuild. Example shape:
//   static const char *kResultsClass = "AppStore.SearchResultsViewModel";
//   static const char *kResultsSel   = "setResults:";
static const char *kResultsClass = NULL; // <-- fill from T1 output
static const char *kResultsSel = NULL;   // <-- fill from T1 output

__attribute__((constructor)) static void GhostProbeInit(void) {
    @autoreleasepool {
        NSLog(@"GhostProbe: loaded. kResultsClass=%s kResultsSel=%s",
              kResultsClass ? kResultsClass : "(unset)",
              kResultsSel ? kResultsSel : "(unset)");
        if (!kResultsClass || !kResultsSel) {
            NSLog(@"GhostProbe: set class+selector from T1-classes.txt, rebuild, rerun.");
            return;
        }
        Class c = objc_getClass(kResultsClass);
        SEL sel = sel_registerName(kResultsSel);
        Method m = class_getInstanceMethod(c, sel);
        if (!m) { NSLog(@"GhostProbe: selector NOT FOUND on %@ — pick another from T1", NSStringFromClass(c)); return; }
        NSLog(@"GhostProbe: confirmed %@ implements %s — wire GhostAdapter here.",
              NSStringFromClass(c), kResultsSel);
    }
}
