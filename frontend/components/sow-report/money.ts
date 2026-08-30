// Currency formatting helper used by RecommendedServices, CostSummary, etc.

const CURRENCY_SYMBOLS: Record<string, string> = { PHP: "₱", USD: "$" };

export function money(value: number, currency: string): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? `${currency} `;
  return `${symbol}${(value ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
