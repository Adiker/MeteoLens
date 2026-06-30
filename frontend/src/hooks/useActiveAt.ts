import { useEffect, useState } from "react";

import { activeAtBucket } from "../api/queries";

/**
 * Current time bucketed to the minute, kept fresh by a timer so an open
 * dashboard advances past warning validity boundaries without a manual
 * interaction. The value only changes when the minute rolls over, so it does
 * not churn the warnings query within a minute.
 */
export function useActiveAt(): string {
  const [value, setValue] = useState(activeAtBucket);
  useEffect(() => {
    const id = window.setInterval(() => setValue(activeAtBucket()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  return value;
}
