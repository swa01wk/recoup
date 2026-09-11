import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "success";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-500 border border-blue-500 disabled:bg-blue-900 disabled:text-blue-500",
  secondary:
    "bg-slate-700 text-slate-200 hover:bg-slate-600 border border-slate-600",
  danger:
    "bg-red-700 text-white hover:bg-red-600 border border-red-600 disabled:bg-red-900 disabled:text-red-500",
  ghost:
    "bg-transparent text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-700",
  success:
    "bg-emerald-700 text-white hover:bg-emerald-600 border border-emerald-600 disabled:bg-emerald-900 disabled:text-emerald-500",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-7 px-3 text-xs rounded",
  md: "h-9 px-4 text-sm rounded-md",
  lg: "h-11 px-6 text-base rounded-lg",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-colors cursor-pointer disabled:cursor-not-allowed",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {loading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}
