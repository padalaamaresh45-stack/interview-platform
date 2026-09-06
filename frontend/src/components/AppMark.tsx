type AppMarkProps = {
  className?: string;
};

/** Monogram brand mark — shared so the nav rail can reuse it later. */
export function AppMark({ className }: AppMarkProps) {
  return (
    <div className={["app-mark", className].filter(Boolean).join(" ")} aria-hidden="true">
      IM
    </div>
  );
}
