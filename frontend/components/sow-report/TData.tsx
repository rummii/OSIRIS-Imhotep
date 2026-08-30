// Shared <td> primitive used by table-heavy sub-sections.
export function TData({
  children,
  mono = false,
  className = "",
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <td className={`px-3 py-2 align-top text-xs ${mono ? "font-mono text-slate-300" : "text-slate-400"} ${className}`}>
      {children}
    </td>
  );
}
