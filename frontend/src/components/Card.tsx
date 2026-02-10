import React from "react";

type Props = React.HTMLAttributes<HTMLDivElement>;

export function Card({ className = "", ...rest }: Props) {
  return (
    <div
      className={`rounded-lg border border-gray-200 bg-white p-4 ${className}`}
      {...rest}
    />
  );
}
