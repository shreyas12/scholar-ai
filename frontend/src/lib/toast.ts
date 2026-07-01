// Minimal toast bus — no dependency. Anywhere in the app can call
// `toast.error(msg)` / `toast.success(msg)`; the <Toaster/> mounted at the root
// subscribes and renders. Kept framework-light on purpose (SA-103).

export type ToastKind = "error" | "success" | "info";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

type Listener = (toasts: Toast[]) => void;

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l(toasts);
}

function push(kind: ToastKind, message: string, ttlMs = 5000) {
  const id = nextId++;
  toasts = [...toasts, { id, kind, message }];
  emit();
  if (ttlMs > 0) setTimeout(() => dismiss(id), ttlMs);
}

export function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  listener(toasts);
  return () => listeners.delete(listener);
}

export const toast = {
  error: (message: string) => push("error", message),
  success: (message: string) => push("success", message),
  info: (message: string) => push("info", message),
};
