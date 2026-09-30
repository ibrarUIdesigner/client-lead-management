export function dateInputValue(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function defaultFollowUpDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 3);
  return dateInputValue(date);
}

export function dateInputToIso(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 9, 0, 0, 0).toISOString();
}

export function isoToDateInput(iso: string): string {
  return dateInputValue(new Date(iso));
}
