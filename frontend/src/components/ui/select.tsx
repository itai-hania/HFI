import * as React from "react";

import { cn } from "@/lib/utils";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          "h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--input)] px-3 text-sm text-[var(--ink)] outline-none transition duration-200 focus:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-60",
          className,
        )}
        {...props}
      >
        {children}
      </select>
    );
  },
);

Select.displayName = "Select";
