import * as React from "react";

import { getAppContext, type AppContext } from "@/lib/context";

/** Access the Django-injected bootstrap context (urls, api, user, sources). */
export function useAppContext(): AppContext {
  return React.useMemo(() => getAppContext(), []);
}
