export default function ClassicLoader({
  className = "",
}: {
  className?: string;
}) {
  return (
    <div
      className={`flex h-10 w-10 animate-spin items-center justify-center rounded-full border-4 border-current border-t-transparent ${className}`}
    />
  );
}
