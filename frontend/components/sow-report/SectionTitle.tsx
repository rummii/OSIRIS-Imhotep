// Shared section header with icon. Used by all SowReport sub-sections.
export function SectionTitle({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
      <span className="grid h-6 w-6 place-items-center rounded-md bg-amber-400/10 border border-amber-400/30 text-amber-400">
        {icon}
      </span>
      {children}
    </div>
  );
}
