"use client";

import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { ArrowUp, BrainCog, Droplets, Filter, Mic, StopCircle } from "lucide-react";

import ClassicLoader from "@/components/ui/loader";
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
        "min-h-[78px] flex w-full resize-none border-none bg-transparent px-3 py-2.5 text-[18px] text-[#442c2d] placeholder:text-[#442c2d]/55 disabled:cursor-not-allowed disabled:opacity-50",
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
      "z-50 overflow-hidden rounded border border-[#e1d1be] bg-[#fbf4eb] px-2.5 py-1 text-xs text-[#442c2d] shadow-[0_10px_30px_-14px_rgba(0,0,0,0.45)]",
      "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1",
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

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
              "group rounded-xl border border-[#e1cfbb] bg-[#f5ebdf]/97 p-2 transition-colors duration-200",
              "shadow-[0_22px_50px_-22px_rgba(0,0,0,0.55),inset_0_1px_0_0_rgba(255,248,239,0.75)]",
              "focus-within:border-[#442c2d]/35 focus-within:bg-[#fbf4eb]",
              isLoading && "border-red-400/60",
              className,
            )}
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
      className={cn("text-[18px]", className)}
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
  onSend?: (message: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
  /** Controlled "use my hair profile" toggle. Defaults to true. */
  personalize?: boolean;
  onPersonalizeChange?: (next: boolean) => void;
  /** Controlled "Think" toggle. When true, the chat backend widens
   * Cohere's `top_k` from 100 → 320 so the tournament has more
   * candidates to discriminate. Judge model is unchanged. */
  thinking?: boolean;
  onThinkingChange?: (next: boolean) => void;
  /** Controlled value for the textarea. */
  value?: string;
  onValueChange?: (next: string) => void;
  /** Optional inline notice rendered to the left of the submit button.
   * Used by the home page to surface the low-count gate without a
   * separate UI component. */
  notice?: React.ReactNode;
}
export const PromptInputBox = React.forwardRef(
  (props: PromptInputBoxProps, ref: React.Ref<HTMLDivElement>) => {
    const {
      onSend = () => {},
      isLoading = false,
      placeholder = "Type your message here…",
      className,
      personalize = true,
      onPersonalizeChange,
      thinking: thinkingProp,
      onThinkingChange,
      value,
      onValueChange,
      notice,
    } = props;
    const [internalInput, setInternalInput] = React.useState("");
    const input = value ?? internalInput;
    const setInput = onValueChange ?? setInternalInput;
    const [isRecording, setIsRecording] = React.useState(false);
    const [internalThinking, setInternalThinking] = React.useState(false);
    const showThink = thinkingProp ?? internalThinking;
    const setShowThink = onThinkingChange ?? setInternalThinking;
    const [showFilter, setShowFilter] = React.useState(false);
    const promptBoxRef = React.useRef<HTMLDivElement>(null);

    // Inject scoped scrollbar CSS once; guard SSR.
    React.useEffect(() => {
      if (document.getElementById("prompt-input-box-styles")) return;
      const sheet = document.createElement("style");
      sheet.id = "prompt-input-box-styles";
      sheet.innerText = styles;
      document.head.appendChild(sheet);
    }, []);

    const handleSubmit = () => {
      if (!input.trim()) return;
      onSend(input);
      // Keep the input populated after submit so the user can read /
      // edit the query while the warning gate is up. The PromptSection
      // unmounts on navigation, so persistence beyond that point is
      // moot.
    };

    const handleStartRecording = () => {};
    const handleStopRecording = (duration: number) => {
      setIsRecording(false);
      onSend(`[Voice message · ${duration}s]`);
    };

    const hasContent = input.trim() !== "";

    const submitTooltip = isLoading
      ? "Stop generation"
      : isRecording
        ? "Stop recording"
        : hasContent
          ? "Send message"
          : "Start voice message";

    return (
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
      >
        <div
          className={cn(
            "transition-opacity duration-300",
            isRecording ? "h-0 overflow-hidden opacity-0" : "opacity-100",
          )}
        >
          <PromptInputTextarea
            placeholder={showThink ? "Think deeply…" : placeholder}
            className="text-[18px]"
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
            <div className="flex items-center">
              <PromptInputAction
                tooltip={
                  personalize
                    ? "Personalized — using your hair profile"
                    : "Generic results — profile off"
                }
              >
              <button
                type="button"
                aria-label="Use my hair profile"
                aria-pressed={personalize}
                onClick={() => onPersonalizeChange?.(!personalize)}
                className={cn(
                  "flex h-[50px] items-center gap-[9px] rounded-xl border px-[15px] transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40",
                  personalize
                    ? "border-transparent bg-[#e7d2b8] text-[#442c2d]"
                    : "border-transparent bg-transparent text-[#442c2d]/80 hover:bg-[#f0e2d1] hover:text-[#442c2d]",
                )}
              >
                <div className="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center">
                  <motion.div
                    animate={{ rotate: personalize ? 360 : 0, scale: personalize ? 1.1 : 1 }}
                    whileHover={{
                      rotate: personalize ? 360 : 15,
                      scale: 1.1,
                      transition: { type: "spring", stiffness: 300, damping: 10 },
                    }}
                    transition={{ type: "spring", stiffness: 260, damping: 25 }}
                  >
                    <Droplets aria-hidden="true" className="h-[24px] w-[24px]" />
                  </motion.div>
                </div>
                <AnimatePresence>
                  {personalize && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex-shrink-0 overflow-hidden whitespace-nowrap text-[18px]"
                    >
                      Profile
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
              </PromptInputAction>

              <PromptInputAction tooltip="Filter results">
              <button
                type="button"
                aria-label="Filter results"
                aria-pressed={showFilter}
                onClick={() => setShowFilter((prev) => !prev)}
                className={cn(
                  "flex h-[50px] items-center gap-[9px] rounded-xl border px-[15px] transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40",
                  showFilter
                    ? "border-transparent bg-[#e7d2b8] text-[#442c2d]"
                    : "border-transparent bg-transparent text-[#442c2d]/80 hover:bg-[#f0e2d1] hover:text-[#442c2d]",
                )}
              >
                <div className="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center">
                  <motion.div
                    animate={{ rotate: showFilter ? 360 : 0, scale: showFilter ? 1.1 : 1 }}
                    whileHover={{
                      rotate: showFilter ? 360 : 15,
                      scale: 1.1,
                      transition: { type: "spring", stiffness: 300, damping: 10 },
                    }}
                    transition={{ type: "spring", stiffness: 260, damping: 25 }}
                  >
                    <Filter aria-hidden="true" className="h-[24px] w-[24px]" />
                  </motion.div>
                </div>
                <AnimatePresence>
                  {showFilter && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex-shrink-0 overflow-hidden whitespace-nowrap text-[18px]"
                    >
                      Filter
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
              </PromptInputAction>

              <CustomDivider />

              <PromptInputAction tooltip="Think deeply">
              <button
                type="button"
                aria-label="Think deeply"
                aria-pressed={showThink}
                onClick={() => setShowThink(!showThink)}
                className={cn(
                  "flex h-[50px] items-center gap-[9px] rounded-xl border px-[15px] transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#442c2d]/40",
                  showThink
                    ? "border-transparent bg-[#e7d2b8] text-[#442c2d]"
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
                    <BrainCog aria-hidden="true" className="h-[24px] w-[24px]" />
                  </motion.div>
                </div>
                <AnimatePresence>
                  {showThink && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{ width: "auto", opacity: 1 }}
                      exit={{ width: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="flex-shrink-0 overflow-hidden whitespace-nowrap text-[18px]"
                    >
                      Think
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
              </PromptInputAction>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {notice && (
              <span
                role="status"
                aria-live="polite"
                className="font-archivo text-[13px] tracking-[0.01em] text-[#442c2d]/80 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
              >
                {notice}
              </span>
            )}
            <PromptInputAction tooltip={submitTooltip}>
            <Button
              variant="default"
              size="icon"
              aria-label={submitTooltip}
              className={cn(
                "h-[50px] w-[50px] rounded-full transition-colors duration-200",
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
                <ClassicLoader className="!h-[24px] !w-[24px] !border-2 !border-current !border-t-transparent" />
              ) : isRecording ? (
                <StopCircle aria-hidden="true" className="h-[27px] w-[27px]" />
              ) : hasContent ? (
                <ArrowUp aria-hidden="true" className="h-[24px] w-[24px]" />
              ) : (
                <Mic aria-hidden="true" className="h-[24px] w-[24px]" />
              )}
            </Button>
          </PromptInputAction>
          </div>
        </PromptInputActions>
      </PromptInput>
    );
  },
);
PromptInputBox.displayName = "PromptInputBox";
