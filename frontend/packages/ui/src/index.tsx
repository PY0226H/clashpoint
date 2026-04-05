import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({
  children,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`echo-btn ${className}`.trim()} {...rest}>
      {children}
    </button>
  );
}

export function TextField({
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`echo-input ${className}`.trim()} {...rest} />;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="echo-section-title">{children}</h2>;
}

export function InlineHint({ children }: { children: ReactNode }) {
  return <p className="echo-inline-hint">{children}</p>;
}
