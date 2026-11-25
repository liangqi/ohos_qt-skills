
## 1. Fix (unused include left over from migration)

The `#include <QtOhosExtras/QOhosAbilityContext>` in `pages/s9_base_equals_window.cpp`
is a leftover from the migration: the file makes no actual `QOhosAbilityContext::` call anywhere; only the evidence
description text mentions `setColorMode()`. The trimmed SDK also has no `QtOhosExtras` header directory → `file not found`.
Simply remove the unused include:

```cpp
#include "demopage.h"
// Originally migrated from QtOhosExtras/QOhosAbilityContext, but this page only mentions
// setColorMode() in its evidence description text; the source never calls any symbol of that
// module, and the in-repo SDK has no QtOhosExtras headers, so the unused include is removed
// to drop the build dependency.
```
