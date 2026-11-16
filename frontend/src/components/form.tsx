import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";

export function PasswordInput({
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { id: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={visible ? "text" : "password"} className="input pr-11" {...props} />
      <button
        type="button"
        className="absolute right-1 top-1 grid h-10 w-10 place-items-center text-muted transition-colors duration-150 hover:text-ink"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-controls={id}
        aria-pressed={visible}
        onClick={() => setVisible((value) => !value)}
      >
        {visible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
      </button>
    </div>
  );
}

export function FormFootnote({ children }: { children: ReactNode }) {
  return <p className="mt-6 text-center text-[13px] text-muted">{children}</p>;
}
