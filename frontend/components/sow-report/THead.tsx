// Shared <th> primitive used by table-heavy sub-sections.
export function THead({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={`px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500 whitespace-nowrap ${className}`}>
      {children}
    </th>
  );
}
