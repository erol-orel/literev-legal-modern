import { CheckCircle2, Info, XCircle } from "lucide-react";

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";
import { useToast, type ToastVariant } from "@/hooks/use-toast";

const ICONS: Record<ToastVariant, typeof Info> = {
  default: Info,
  success: CheckCircle2,
  destructive: XCircle,
};

const ICON_CLASSES: Record<ToastVariant, string> = {
  default: "text-primary",
  success: "text-success",
  destructive: "text-destructive",
};

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, variant = "default", open }) => {
        const Icon = ICONS[variant];
        return (
          <Toast
            key={id}
            variant={variant}
            open={open}
            onOpenChange={(next) => {
              if (!next) dismiss(id);
            }}
          >
            <Icon className={`mt-0.5 size-5 shrink-0 ${ICON_CLASSES[variant]}`} />
            <div className="grid gap-1">
              {title && <ToastTitle>{title}</ToastTitle>}
              {description && <ToastDescription>{description}</ToastDescription>}
            </div>
            <ToastClose />
          </Toast>
        );
      })}
      <ToastViewport />
    </ToastProvider>
  );
}
