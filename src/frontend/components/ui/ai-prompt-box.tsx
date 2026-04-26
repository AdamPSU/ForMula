"use client";

import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowUp, Paperclip, Square, X, StopCircle, Mic, Globe, BrainCog } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const cn = (...classes: (string | undefined | null | false)[]) =>
  classes.filter(Boolean).join(" ");

// Scoped scrollbar styling for the warm surface treatment.
const styles = `
  textarea::-webkit-scrollbar {
    width: 6px;
  }
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  textarea::-webkit-scrollbar-thumb {
    background-color: rgba(120, 87, 55, 0.24);
    border-radius: 3px;
  }
  textarea::-webkit-scrollbar-thumb:hover {
    background-color: rgba(120, 87, 55, 0.4);
  }
`;

// Textarea ---------------------------------------------------------------

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  className?: string;
}
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        "min-h-[66px] flex w-full resize-none border-none bg-transparent px-3 py-2.5 text-base text-[#442c2d] placeholder:text-[#442c2d]/55 disabled:cursor-not-allowed disabled:opacity-50",
        "focus:outline-none focus-visible:outline-none",
        className,
      )}
      ref={ref}
      rows={1}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

// Tooltip ----------------------------------------------------------------

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-lg border border-[#e1d1be] bg-[#fbf4eb] px-2.5 py-1 text-xs text-[#442c2d] shadow-[0_10px_30px_-14px_rgba(0,0,0,0.45)]",
      "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1",
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

// Dialog (image preview) -------------------------------------------------

const Dialog = DialogPrimitive.Root;
const DialogPortal = DialogPrimitive.Portal;
const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/60 backdrop-blur-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid w-full max-w-[90vw] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-2xl border border-[#e1d1be] bg-[#f5ebdf] p-0 shadow-[0_30px_80px_-24px_rgba(0,0,0,0.65)] duration-300 md:max-w-[1200px]",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close
        aria-label="Close preview"
        className="absolute right-4 top-4 z-10 rounded-full bg-[#fff8ef]/95 p-2 text-[#442c2d] hover:bg-[#ffffff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40"
      >
        <X aria-hidden="true" className="h-5 w-5" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight text-[#442c2d]", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

// Button -----------------------------------------------------------------

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const variantClasses = {
      default: "bg-[#442c2d] text-[#fff9f0] hover:bg-[#442c2d]/92",
      outline:
        "border border-[#ddcbb6] bg-[#f8efe5]/92 text-[#442c2d] hover:bg-[#fff8ef]",
      ghost: "bg-transparent text-[#442c2d]/80 hover:bg-[#f0e2d1]",
    };
    const sizeClasses = {
      default: "h-10 px-4 py-2",
      sm: "h-8 px-3 text-sm",
      lg: "h-12 px-6",
      icon: "h-8 w-8 rounded-full aspect-square",
    };
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40 focus-visible:ring-offset-0",
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

// Voice recorder ---------------------------------------------------------

interface VoiceRecorderProps {
  isRecording: boolean;
  onStartRecording: () => void;
  onStopRecording: (duration: number) => void;
  visualizerBars?: number;
}
const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  isRecording,
  onStartRecording,
  onStopRecording,
  visualizerBars = 32,
}) => {
  const [time, setTime] = React.useState(0);
  const timerRef = React.useRef<NodeJS.Timeout | null>(null);
  const barStyles = React.useMemo(
    () =>
      Array.from({ length: visualizerBars }, (_, i) => ({
        height: `${15 + ((i * 23) % 70)}%`,
        animationDelay: `${i * 0.05}s`,
        animationDuration: `${0.55 + ((i * 7) % 6) * 0.1}s`,
      })),
    [visualizerBars],
  );

  React.useEffect(() => {
    if (isRecording) {
      onStartRecording();
      timerRef.current = setInterval(() => setTime((t) => t + 1), 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      onStopRecording(time);
      setTime(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording, time, onStartRecording, onStopRecording]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div
      className={cn(
        "flex w-full flex-col items-center justify-center py-3 transition-opacity duration-300",
        isRecording ? "opacity-100" : "h-0 opacity-0",
      )}
      aria-live="polite"
    >
      <div className="mb-3 flex items-center gap-2">
        <div className="h-2 w-2 animate-pulse rounded-full bg-red-400 motion-reduce:animate-none" />
        <span className="font-mono text-sm text-[#442c2d]">{formatTime(time)}</span>
      </div>
      <div className="flex h-10 w-full items-center justify-center gap-0.5 px-4">
        {barStyles.map((style, i) => (
          <div
            key={i}
            className="w-0.5 animate-pulse rounded-full bg-[#442c2d]/60 motion-reduce:animate-none"
            style={style}
          />
        ))}
      </div>
    </div>
  );
};

// Image preview dialog ---------------------------------------------------

interface ImageViewDialogProps {
  imageUrl: string | null;
  onClose: () => void;
}
const ImageViewDialog: React.FC<ImageViewDialogProps> = ({ imageUrl, onClose }) => {
  if (!imageUrl) return null;
  return (
    <Dialog open={!!imageUrl} onOpenChange={onClose}>
      <DialogContent className="max-w-[90vw] border-none bg-transparent p-0 shadow-none backdrop-blur-none md:max-w-[1200px]">
        <DialogTitle className="sr-only">Image preview</DialogTitle>
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="relative overflow-hidden rounded-2xl border border-[#e1d1be] bg-[#f5ebdf] shadow-[0_30px_80px_-24px_rgba(0,0,0,0.6)]"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt="Attached file, full preview"
            className="max-h-[80vh] w-full rounded-2xl object-contain"
          />
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};

// Context ----------------------------------------------------------------

interface PromptInputContextType {
  isLoading: boolean;
  value: string;
  setValue: (value: string) => void;
  maxHeight: number | string;
  onSubmit?: () => void;
  disabled?: boolean;
}
const PromptInputContext = React.createContext<PromptInputContextType>({
  isLoading: false,
  value: "",
  setValue: () => {},
  maxHeight: 240,
  onSubmit: undefined,
  disabled: false,
});
function usePromptInput() {
  const context = React.useContext(PromptInputContext);
  if (!context) throw new Error("usePromptInput must be used within a PromptInput");
  return context;
}

interface PromptInputProps {
  isLoading?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  maxHeight?: number | string;
  onSubmit?: () => void;
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}
const PromptInput = React.forwardRef<HTMLDivElement, PromptInputProps>(
  (
    {
      className,
      isLoading = false,
      maxHeight = 240,
      value,
      onValueChange,
      onSubmit,
      children,
      disabled = false,
      onDragOver,
      onDragLeave,
      onDrop,
    },
    ref,
  ) => {
    const [internalValue, setInternalValue] = React.useState(value || "");
    const handleChange = (newValue: string) => {
      setInternalValue(newValue);
      onValueChange?.(newValue);
    };
    return (
      <TooltipProvider delayDuration={200}>
        <PromptInputContext.Provider
          value={{
            isLoading,
            value: value ?? internalValue,
            setValue: onValueChange ?? handleChange,
            maxHeight,
            onSubmit,
            disabled,
          }}
        >
          <div
            ref={ref}
            className={cn(
              "group rounded-3xl border border-[#e1cfbb] bg-[#f5ebdf]/97 p-2 transition-colors duration-200",
              "shadow-[0_22px_50px_-22px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,248,239,0.75)]",
              "focus-within:border-[#442c2d]/35 focus-within:bg-[#fbf4eb]",
              isLoading && "border-red-400/60",
              className,
            )}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            {children}
          </div>
        </PromptInputContext.Provider>
      </TooltipProvider>
    );
  },
);
PromptInput.displayName = "PromptInput";

// Textarea wrapper -------------------------------------------------------

interface PromptInputTextareaProps {
  disableAutosize?: boolean;
  placeholder?: string;
  ariaLabel?: string;
}
const PromptInputTextarea: React.FC<
  PromptInputTextareaProps & React.ComponentProps<typeof Textarea>
> = ({ className, onKeyDown, disableAutosize = false, placeholder, ariaLabel, ...props }) => {
  const { value, setValue, maxHeight, onSubmit, disabled } = usePromptInput();
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (disableAutosize || !textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height =
      typeof maxHeight === "number"
        ? `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
        : `min(${textareaRef.current.scrollHeight}px, ${maxHeight})`;
  }, [value, maxHeight, disableAutosize]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
    onKeyDown?.(e);
  };

  return (
    <Textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      className={cn("text-base", className)}
      disabled={disabled}
      placeholder={placeholder}
      aria-label={ariaLabel ?? "Message"}
      autoComplete="off"
      {...props}
    />
  );
};

// Actions row ------------------------------------------------------------

const PromptInputActions: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => (
  <div className={cn("flex items-center gap-2", className)} {...props}>
    {children}
  </div>
);

interface PromptInputActionProps extends React.ComponentProps<typeof Tooltip> {
  tooltip: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
}
const PromptInputAction: React.FC<PromptInputActionProps> = ({
  tooltip,
  children,
  className,
  side = "top",
  ...props
}) => {
  const { disabled } = usePromptInput();
  return (
    <Tooltip {...props}>
      <TooltipTrigger asChild disabled={disabled}>
        {children}
      </TooltipTrigger>
      <TooltipContent side={side} className={className}>
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
};

// Thin gradient hairline divider, sharpened with a clip-path diamond pinch —
// keeps the editorial kebab between toggle chips rather than a flat pipe.
const CustomDivider: React.FC = () => (
  <div aria-hidden="true" className="relative mx-1 h-5 w-px">
    <div
      className="absolute inset-0 rounded-full bg-gradient-to-t from-transparent via-[#442c2d]/40 to-transparent"
      style={{
        clipPath:
          "polygon(0% 0%, 100% 0%, 100% 40%, 140% 50%, 100% 60%, 100% 100%, 0% 100%, 0% 60%, -40% 50%, 0% 40%)",
      }}
    />
  </div>
);

// Main component ---------------------------------------------------------

interface PromptInputBoxProps {
  onSend?: (message: string, files?: File[]) => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}
export const PromptInputBox = React.forwardRef(
  (props: PromptInputBoxProps, ref: React.Ref<HTMLDivElement>) => {
    const {
      onSend = () => {},
      isLoading = false,
      placeholder = "Type your message here…",
      className,
    } = props;
    const [input, setInput] = React.useState("");
    const [files, setFiles] = React.useState<File[]>([]);
    const [filePreviews, setFilePreviews] = React.useState<{ [key: string]: string }>({});
    const [selectedImage, setSelectedImage] = React.useState<string | null>(null);
    const [isRecording, setIsRecording] = React.useState(false);
    const [showSearch, setShowSearch] = React.useState(false);
    const [showThink, setShowThink] = React.useState(false);
    const uploadInputRef = React.useRef<HTMLInputElement>(null);
    const promptBoxRef = React.useRef<HTMLDivElement>(null);

    // Inject scoped scrollbar CSS once; guard SSR.
    React.useEffect(() => {
      if (document.getElementById("prompt-input-box-styles")) return;
      const sheet = document.createElement("style");
      sheet.id = "prompt-input-box-styles";
      sheet.innerText = styles;
      document.head.appendChild(sheet);
    }, []);

    const handleToggleChange = (value: "search" | "think") => {
      if (value === "search") {
        setShowSearch((prev) => !prev);
        setShowThink(false);
      } else {
        setShowThink((prev) => !prev);
        setShowSearch(false);
      }
    };

    const isImageFile = (file: File) => file.type.startsWith("image/");

    const processFile = React.useCallback((file: File) => {
      if (!isImageFile(file)) return;
      if (file.size > 10 * 1024 * 1024) return;
      setFiles([file]);
      const reader = new FileReader();
      reader.onload = (e) => setFilePreviews({ [file.name]: e.target?.result as string });
      reader.readAsDataURL(file);
    }, []);

    const handleDragOver = React.useCallback((e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    }, []);
    const handleDragLeave = React.useCallback((e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    }, []);
    const handleDrop = React.useCallback(
      (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const dropped = Array.from(e.dataTransfer.files).filter(isImageFile);
        if (dropped.length > 0) processFile(dropped[0]);
      },
      [processFile],
    );

    const handleRemoveFile = (index: number) => {
      const fileToRemove = files[index];
      if (fileToRemove && filePreviews[fileToRemove.name]) setFilePreviews({});
      setFiles([]);
    };

    const openImageModal = (imageUrl: string) => setSelectedImage(imageUrl);

    const handlePaste = React.useCallback(
      (e: ClipboardEvent) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.indexOf("image") !== -1) {
            const file = items[i].getAsFile();
            if (file) {
              e.preventDefault();
              processFile(file);
              break;
            }
          }
        }
      },
      [processFile],
    );
    React.useEffect(() => {
      document.addEventListener("paste", handlePaste);
      return () => document.removeEventListener("paste", handlePaste);
    }, [handlePaste]);

    const handleSubmit = () => {
      if (!input.trim() && files.length === 0) return;
      let messagePrefix = "";
      if (showSearch) messagePrefix = "[Search: ";
      else if (showThink) messagePrefix = "[Think: ";
      const formatted = messagePrefix ? `${messagePrefix}${input}]` : input;
      onSend(formatted, files);
      setInput("");
      setFiles([]);
      setFilePreviews({});
    };

    const handleStartRecording = () => {};
    const handleStopRecording = (duration: number) => {
      setIsRecording(false);
      onSend(`[Voice message · ${duration}s]`, []);
    };

    const hasContent = input.trim() !== "" || files.length > 0;

    const submitTooltip = isLoading
      ? "Stop generation"
      : isRecording
        ? "Stop recording"
        : hasContent
          ? "Send message"
          : "Start voice message";

    return (
      <>
        <PromptInput
          value={input}
          onValueChange={setInput}
          isLoading={isLoading}
          onSubmit={handleSubmit}
          className={cn(
            "w-full transition-colors duration-300",
            isRecording && "border-red-400/60",
            className,
          )}
          disabled={isLoading || isRecording}
          ref={ref || promptBoxRef}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {files.length > 0 && !isRecording && (
            <div className="flex flex-wrap gap-2 p-0 pb-1">
              {files.map((file, index) => (
                <div key={index} className="group relative">
                  {file.type.startsWith("image/") && filePreviews[file.name] && (
                    <div
                      className="h-16 w-16 cursor-pointer overflow-hidden rounded-xl border border-[#e0ceba]"
                      onClick={() => openImageModal(filePreviews[file.name])}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={filePreviews[file.name]}
                        alt={`Attached file: ${file.name}`}
                        className="h-full w-full object-cover"
                      />
                      <button
                        type="button"
                        aria-label={`Remove ${file.name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveFile(index);
                        }}
                        className="absolute right-1 top-1 rounded-full bg-[#fff8ef] p-0.5 text-[#442c2d] hover:bg-[#ffffff] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40"
                      >
                        <X aria-hidden="true" className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div
            className={cn(
              "transition-opacity duration-300",
              isRecording ? "h-0 overflow-hidden opacity-0" : "opacity-100",
            )}
          >
            <PromptInputTextarea
              placeholder={
                showSearch ? "Search the web…" : showThink ? "Think deeply…" : placeholder
              }
              className="text-base"
            />
          </div>

          {isRecording && (
            <VoiceRecorder
              isRecording={isRecording}
              onStartRecording={handleStartRecording}
              onStopRecording={handleStopRecording}
            />
          )}

          <PromptInputActions className="flex items-center justify-between gap-2 p-0 pt-2">
            <div
              className={cn(
                "flex items-center gap-1 transition-opacity duration-300",
                isRecording ? "invisible h-0 opacity-0" : "visible opacity-100",
              )}
            >
              <PromptInputAction tooltip="Upload image">
                <button
                  type="button"
                  aria-label="Upload image"
                  onClick={() => uploadInputRef.current?.click()}
                  disabled={isRecording}
                  className="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full text-[#442c2d]/80 transition-colors hover:bg-[#f0e2d1] hover:text-[#442c2d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40"
                >
                  <Paperclip aria-hidden="true" className="h-[27px] w-[27px]" />
                  <input
                    ref={uploadInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0)
                        processFile(e.target.files[0]);
                      if (e.target) e.target.value = "";
                    }}
                    accept="image/*"
                  />
                </button>
              </PromptInputAction>

              <div className="flex items-center">
                <button
                  type="button"
                  aria-label="Search the web"
                  aria-pressed={showSearch}
                  onClick={() => handleToggleChange("search")}
                  className={cn(
                    "flex h-12 items-center gap-1.5 rounded-full border px-3 py-1 transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40",
                    showSearch
                      ? "border-[#442c2d] bg-[#e7d2b8] text-[#442c2d]"
                      : "border-transparent bg-transparent text-[#442c2d]/80 hover:bg-[#f0e2d1] hover:text-[#442c2d]",
                  )}
                >
                  <div className="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center">
                    <motion.div
                      animate={{ rotate: showSearch ? 360 : 0, scale: showSearch ? 1.1 : 1 }}
                      whileHover={{
                        rotate: showSearch ? 360 : 15,
                        scale: 1.1,
                        transition: { type: "spring", stiffness: 300, damping: 10 },
                      }}
                      transition={{ type: "spring", stiffness: 260, damping: 25 }}
                    >
                      <Globe aria-hidden="true" className="h-[27px] w-[27px]" />
                    </motion.div>
                  </div>
                  <AnimatePresence>
                    {showSearch && (
                      <motion.span
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: "auto", opacity: 1 }}
                        exit={{ width: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="flex-shrink-0 overflow-hidden whitespace-nowrap text-xs"
                      >
                        Search
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>

                <CustomDivider />

                <button
                  type="button"
                  aria-label="Think deeply"
                  aria-pressed={showThink}
                  onClick={() => handleToggleChange("think")}
                  className={cn(
                    "flex h-12 items-center gap-1.5 rounded-full border px-3 py-1 transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40",
                    showThink
                      ? "border-[#442c2d] bg-[#e7d2b8] text-[#442c2d]"
                      : "border-transparent bg-transparent text-[#442c2d]/80 hover:bg-[#f0e2d1] hover:text-[#442c2d]",
                  )}
                >
                  <div className="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center">
                    <motion.div
                      animate={{ rotate: showThink ? 360 : 0, scale: showThink ? 1.1 : 1 }}
                      whileHover={{
                        rotate: showThink ? 360 : 15,
                        scale: 1.1,
                        transition: { type: "spring", stiffness: 300, damping: 10 },
                      }}
                      transition={{ type: "spring", stiffness: 260, damping: 25 }}
                    >
                      <BrainCog aria-hidden="true" className="h-[27px] w-[27px]" />
                    </motion.div>
                  </div>
                  <AnimatePresence>
                    {showThink && (
                      <motion.span
                        initial={{ width: 0, opacity: 0 }}
                        animate={{ width: "auto", opacity: 1 }}
                        exit={{ width: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="flex-shrink-0 overflow-hidden whitespace-nowrap text-xs"
                      >
                        Think
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              </div>
            </div>

            <PromptInputAction tooltip={submitTooltip}>
              <Button
                variant="default"
                size="icon"
                aria-label={submitTooltip}
                className={cn(
                  "h-12 w-12 rounded-full transition-colors duration-200",
                  isRecording
                    ? "bg-[#e7d2b8] text-red-800 hover:bg-[#f0deca]"
                    : hasContent
                      ? "bg-[#442c2d] text-[#fff9f0] hover:bg-[#442c2d]/92"
                      : "bg-[#e7d2b8] text-[#442c2d]/80 hover:bg-[#f0deca] hover:text-[#442c2d]",
                )}
                onClick={() => {
                  if (isRecording) setIsRecording(false);
                  else if (hasContent) handleSubmit();
                  else setIsRecording(true);
                }}
                disabled={isLoading && !hasContent}
              >
                {isLoading ? (
                  <Square
                    aria-hidden="true"
                    className="h-[27px] w-[27px] animate-pulse fill-[#fff9f0] motion-reduce:animate-none"
                  />
                ) : isRecording ? (
                  <StopCircle aria-hidden="true" className="h-[30px] w-[30px]" />
                ) : hasContent ? (
                  <ArrowUp aria-hidden="true" className="h-[27px] w-[27px]" />
                ) : (
                  <Mic aria-hidden="true" className="h-[27px] w-[27px]" />
                )}
              </Button>
            </PromptInputAction>
          </PromptInputActions>
        </PromptInput>

        <ImageViewDialog imageUrl={selectedImage} onClose={() => setSelectedImage(null)} />
      </>
    );
  },
);
PromptInputBox.displayName = "PromptInputBox";
