import { Badge } from "@/components/ui/badge";
import { formatLifecycleLabel, lifecycleBadgeVariant } from "@/lib/recoup-ui-rules";

interface StatusBadgeProps {
  state: string;
  className?: string;
}

export function StatusBadge({ state, className }: StatusBadgeProps) {
  return (
    <Badge variant={lifecycleBadgeVariant(state)} className={className ?? "normal-case"}>
      {formatLifecycleLabel(state)}
    </Badge>
  );
}
