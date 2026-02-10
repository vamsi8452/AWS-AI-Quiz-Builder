import React from "react";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
  isLoading?: boolean;
};

const base =
  "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed";

const variants: Record<NonNullable<Props["variant"]>, string> = {
  primary: "bg-black text-white hover:bg-gray-800 focus:ring-gray-400",
  secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-300",
  danger: "bg-red-600 text-white hover:bg-red-700 focus:ring-red-300",
};

export function Button({
  variant = "primary",
  isLoading = false,
  children,
  disabled,
  ...rest
}: Props) {
  return (
    <button
      className={`${base} ${variants[variant]}`}
      disabled={disabled || isLoading}
      {...rest}
    >
      {isLoading ? "Loading..." : children}
    </button>
  );
}
