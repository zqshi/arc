type QuotaListener = (detail: string) => void;

class QuotaEvents {
  private listeners = new Set<QuotaListener>();

  on(fn: QuotaListener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit(detail: string) {
    this.listeners.forEach((fn) => fn(detail));
  }
}

export const quotaEvents = new QuotaEvents();
