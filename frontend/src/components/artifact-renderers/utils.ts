export function asString(v: unknown): string {
  if (typeof v === 'string') return v;
  if (v == null) return '';
  return JSON.stringify(v, null, 2);
}

export function asArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  return [];
}
