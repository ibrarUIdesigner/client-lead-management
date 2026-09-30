export function mailtoUrl(email: string, subject: string, body: string): string {
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export function outreachText(subject: string, body: string): string {
  const heading = subject.trim() ? `Subject: ${subject.trim()}` : "";
  return [heading, body.trim()].filter(Boolean).join("\n\n");
}

export async function copyOutreach(subject: string, body: string): Promise<void> {
  await navigator.clipboard.writeText(outreachText(subject, body));
}
