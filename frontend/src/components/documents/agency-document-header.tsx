type AgencyDocumentHeaderProps = {
  agencyName: string;
  agencyLogo?: string | null;
  title: string;
  subtitle?: string;
  compact?: boolean;
};

export function AgencyDocumentHeader({
  agencyName,
  agencyLogo,
  title,
  subtitle,
  compact = false,
}: Readonly<AgencyDocumentHeaderProps>) {
  return (
    <header className={compact ? "flex min-w-0 items-center gap-3 text-start" : "border-b-2 border-slate-900 pb-5 text-center"}>
      {agencyLogo && (
        // A plain image is intentional here because it must be embedded by the browser when printing.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={agencyLogo}
          alt={`${agencyName} logo`}
          className={compact ? "h-12 w-16 shrink-0 object-contain" : "mx-auto mb-3 max-h-20 max-w-48 object-contain"}
        />
      )}
      <div className="min-w-0">
        <p className={compact ? "text-sm font-bold" : "text-xl font-bold"}>{agencyName}</p>
        <h1 className={compact ? "text-base font-bold" : "mt-2 text-2xl font-bold"}>{title}</h1>
        {subtitle && <p className={compact ? "text-xs" : "mt-1 text-sm"}>{subtitle}</p>}
      </div>
    </header>
  );
}
