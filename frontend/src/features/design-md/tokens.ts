export type ColorToken = {
  name: string;
  hex: string;
};

export type TypeToken = {
  name: string;
  size: string;
  weight: number | null;
};

export type RadiusToken = {
  name: string;
  px: number;
  full: boolean;
};

export type SpacingToken = {
  name: string;
  px: number;
};

export type DesignTokens = {
  summary: string;
  colors: ColorToken[];
  type: TypeToken[];
  radii: RadiusToken[];
  spacing: SpacingToken[];
};

type SectionKind = "colors" | "type" | "spacing" | "radius";

const WEIGHTS: Array<[RegExp, number]> = [
  [/extra[-\s]?bold|\b800\b|\bw800\b/i, 800],
  [/semi[-\s]?bold|\b600\b|\bw600\b/i, 600],
  [/extra[-\s]?light|\b200\b/i, 200],
  [/\bmedium\b|\b500\b|\bw500\b/i, 500],
  [/\bregular\b|\bnormal\b|\b400\b|\bw400\b/i, 400],
  [/\blight\b|\b300\b/i, 300],
  [/\bthin\b|\b100\b/i, 100],
  [/\bblack\b|\b900\b/i, 900],
  [/\bbold\b|\b700\b|\bw700\b/i, 700],
];

export function extractDesignTokens(source: string): DesignTokens {
  const sections = collectSections(source);
  return {
    summary: extractSummary(source),
    colors: parseColors(sections.colors),
    type: parseType(sections.type),
    radii: parseRadii(sections.radius),
    spacing: parseSpacing(sections.spacing),
  };
}

export function hasDesignTokens(tokens: DesignTokens): boolean {
  return (
    tokens.colors.length > 0 ||
    tokens.type.length > 0 ||
    tokens.radii.length > 0 ||
    tokens.spacing.length > 0
  );
}

function collectSections(source: string): Record<SectionKind, string[]> {
  const buckets: Record<SectionKind, string[]> = {
    colors: [],
    type: [],
    spacing: [],
    radius: [],
  };
  let current: SectionKind | null = null;
  let fence = false;

  for (const line of source.replaceAll("\r\n", "\n").split("\n")) {
    if (line.trim().startsWith("```")) {
      fence = !fence;
      continue;
    }
    if (!fence) {
      const heading = /^(#{1,2})\s+(.+)$/.exec(line.trim());
      if (heading) {
        current = sectionKind(heading[2] ?? "");
        continue;
      }
    }
    if (current) {
      buckets[current].push(line);
    }
  }

  return buckets;
}

function sectionKind(title: string): SectionKind | null {
  const text = title.toLowerCase();
  if (/color|palette|colour/.test(text)) {
    return "colors";
  }
  if (/typograph|type scale|\btype\b/.test(text)) {
    return "type";
  }
  if (/spacing|space scale/.test(text)) {
    return "spacing";
  }
  if (/radius|radii|corner/.test(text)) {
    return "radius";
  }
  return null;
}

function extractSummary(source: string): string {
  const lines = source.replaceAll("\r\n", "\n").split("\n");
  let taking = false;
  const preferred: string[] = [];
  const fallback: string[] = [];
  let fence = false;

  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("```")) {
      fence = !fence;
      continue;
    }
    if (fence) {
      continue;
    }
    if (/^#{1,3}\s+/.test(line)) {
      const title = line.replace(/^#{1,3}\s+/, "");
      if (/overview|about|visual style|philosophy|voice|direction/i.test(title)) {
        taking = true;
        preferred.length = 0;
        continue;
      }
      if (taking && preferred.length > 0) {
        break;
      }
      continue;
    }
    if (!line || line === "---" || /^[-*]\s+/.test(line) || line.startsWith("|")) {
      if (taking && preferred.length > 0) {
        break;
      }
      if (fallback.length > 0) {
        break;
      }
      continue;
    }
    const sentence = plain(line);
    if (!sentence) {
      continue;
    }
    if (taking) {
      preferred.push(sentence);
    } else if (fallback.length < 3) {
      fallback.push(sentence);
    }
  }

  const summary = (preferred.length > 0 ? preferred : fallback).join(" ");
  return summary.length > 280 ? `${summary.slice(0, 277).trimEnd()}...` : summary;
}

function parseColors(lines: string[]): ColorToken[] {
  const colors: ColorToken[] = [];
  const seen = new Set<string>();
  let pending = "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed === "---" || trimmed.startsWith("|")) {
      continue;
    }
    const hexes = [
      ...trimmed.matchAll(/#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b/g),
    ];
    if (hexes.length === 0) {
      const label = labelFrom(trimmed);
      if (label && label.length <= 40) {
        pending = label;
      }
      continue;
    }
    for (const match of hexes) {
      const hex = normalizeHex(match[0]);
      if (seen.has(hex)) {
        continue;
      }
      const before = trimmed.slice(0, match.index ?? 0);
      let name = labelFrom(before);
      if (!name || name.length > 40) {
        name = pending;
      }
      if (!name) {
        name = hex.toUpperCase();
      }
      seen.add(hex);
      colors.push({ name, hex });
    }
    pending = "";
  }

  return colors.slice(0, 16);
}

function parseType(lines: string[]): TypeToken[] {
  const tokens: TypeToken[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed === "---" || /^\|?\s*:?-{3,}/.test(trimmed)) {
      continue;
    }

    let name = "";
    let size: string | null = null;
    let weightSource = trimmed;

    if (trimmed.includes("|")) {
      const cells = trimmed
        .split("|")
        .map((cell) => cell.trim())
        .filter((cell) => cell.length > 0);
      if (cells.length < 2) {
        continue;
      }
      if (/^(token|name|style)$/i.test(cells[0] ?? "") || /^size$/i.test(cells[1] ?? "")) {
        continue;
      }
      name = labelFrom(cells[0] ?? "");
      size = firstFontSize(cells.slice(1).join(" "))?.raw ?? null;
      weightSource = cells.join(" ");
    } else {
      const sized = firstFontSize(trimmed);
      if (!sized) {
        continue;
      }
      name = labelFrom(trimmed.slice(0, sized.index));
      size = sized.raw;
    }

    if (!size || !name || name.length > 32) {
      continue;
    }
    if (/^(use|avoid|base unit|primary font|weights|typography scale)$/i.test(name)) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    tokens.push({ name, size, weight: weightFrom(weightSource) });
  }

  return tokens.slice(0, 12);
}

function parseRadii(lines: string[]): RadiusToken[] {
  const tokens: RadiusToken[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed === "---" || /^do not\b/i.test(trimmed)) {
      continue;
    }
    const sized = firstFontSize(trimmed);
    const bold = /\*\*([^*]+)\*\*/.exec(trimmed);
    let name = bold?.[1]?.trim() ?? "";
    if (!name && sized) {
      name = labelFrom(trimmed.slice(0, sized.index));
    }
    if (!name || name.length > 32 || /\d+(?:\.\d+)?\s*(px|rpx|rem|em)\b/i.test(name)) {
      continue;
    }
    const px = sized ? Number.parseFloat(sized.raw) : null;
    const full = /^(full|pill|circle|round)$/i.test(name) || (px !== null && px >= 999);
    if (px === null && !full) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    tokens.push({ name, px: px ?? 999, full });
  }

  return tokens.slice(0, 8);
}

function parseSpacing(lines: string[]): SpacingToken[] {
  const tokens: SpacingToken[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed === "---") {
      continue;
    }
    const unmarked = trimmed.replaceAll("**", "");
    if (/^(base unit|use an?)\b/i.test(unmarked)) {
      continue;
    }
    const sized = firstFontSize(trimmed);
    if (!sized) {
      continue;
    }
    const bold = /\*\*([^*]+)\*\*/.exec(trimmed);
    let name = "";
    if (bold && !/\d/.test(bold[1] ?? "")) {
      name = bold[1]?.trim() ?? "";
    }
    if (!name) {
      name = labelFrom(trimmed.slice(0, sized.index));
    }
    if (!name) {
      name = sized.raw;
    }
    if (name.length > 24 || /^(base unit|use)$/i.test(name)) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    const px = Number.parseFloat(sized.raw);
    if (!Number.isFinite(px) || px <= 0) {
      continue;
    }
    seen.add(key);
    tokens.push({ name, px });
  }

  return tokens.slice(0, 8);
}

function firstFontSize(text: string): { raw: string; index: number } | null {
  const pattern = /(\d+(?:\.\d+)?)\s*(px|rpx|rem|em)\b/gi;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > 0 && text[index - 1] === "-") {
      continue;
    }
    const before = text.slice(Math.max(0, index - 28), index);
    if (/letter-spacing|line-height|tracking|leading/i.test(before)) {
      continue;
    }
    const unit = match[2]?.toLowerCase() ?? "px";
    return { raw: `${match[1] ?? ""}${unit}`, index };
  }
  return null;
}

function weightFrom(text: string): number | null {
  for (const [pattern, weight] of WEIGHTS) {
    if (pattern.test(text)) {
      return weight;
    }
  }
  return null;
}

function labelFrom(value: string): string {
  const bold = /\*\*([^*]+)\*\*/.exec(value);
  return plain(bold?.[1] ?? value)
    .replace(/^[-*]\s+/, "")
    .replace(/[:(]\s*$/, "")
    .trim();
}

function plain(value: string): string {
  return value.replaceAll("**", "").replaceAll("`", "").replace(/\s+/g, " ").trim();
}

function normalizeHex(input: string): string {
  let body = input.slice(1).toLowerCase();
  if (body.length === 3 || body.length === 4) {
    body = [...body].map((character) => character + character).join("");
  }
  if (body.length === 8) {
    body = body.slice(0, 6);
  }
  return `#${body}`;
}
