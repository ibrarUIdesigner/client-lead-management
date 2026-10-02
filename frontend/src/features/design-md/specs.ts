import type { ColorToken } from "./tokens";

export type SpecNote = {
  name: string;
  detail: string;
};

export type SpecGroup = {
  summary: string;
  items: SpecNote[];
};

export type GuideSpecs = {
  cards: SpecGroup;
  inputs: SpecGroup;
  buttons: SpecGroup;
  components: SpecNote[];
  chips: SpecNote[];
  elevation: SpecNote[];
  dos: string[];
  donts: string[];
  responsive: SpecNote[];
};

type Block = {
  level: number;
  title: string;
  lines: string[];
  children: Block[];
};

type SpecKind =
  "cards" | "inputs" | "buttons" | "components" | "chips" | "elevation" | "rules" | "responsive";

export function extractGuideSpecs(source: string): GuideSpecs {
  const specs: GuideSpecs = {
    cards: emptyGroup(),
    inputs: emptyGroup(),
    buttons: emptyGroup(),
    components: [],
    chips: [],
    elevation: [],
    dos: [],
    donts: [],
    responsive: [],
  };

  for (const block of parseBlocks(source)) {
    collect(block, specs);
  }

  fillGaps(source, specs);

  specs.components = specs.components.slice(0, 12);
  specs.chips = specs.chips.slice(0, 8);
  specs.elevation = specs.elevation.slice(0, 9);
  specs.responsive = specs.responsive.slice(0, 8);
  specs.dos = specs.dos.slice(0, 12);
  specs.donts = specs.donts.slice(0, 8);
  return specs;
}

export function hasGuideSpecs(specs: GuideSpecs): boolean {
  return (
    specs.cards.items.length > 0 ||
    specs.cards.summary.length > 0 ||
    specs.inputs.items.length > 0 ||
    specs.inputs.summary.length > 0 ||
    specs.buttons.items.length > 0 ||
    specs.buttons.summary.length > 0 ||
    specs.components.length > 0 ||
    specs.chips.length > 0 ||
    specs.elevation.length > 0 ||
    specs.dos.length > 0 ||
    specs.donts.length > 0 ||
    specs.responsive.length > 0
  );
}

function fillGaps(source: string, specs: GuideSpecs): void {
  if (specs.inputs.items.length === 0 && !specs.inputs.summary) {
    const lines = mentionLines(source, /\binputs?\b/i);
    const rule = lines.find((line) => /^use\b/i.test(line));
    const radii = lines.filter((line) => /\(.*(?:px|rpx)\)/i.test(line));
    specs.inputs.summary = rule ?? "";
    specs.inputs.items = (radii.length > 0 ? radii : lines.filter((line) => line !== rule))
      .slice(0, 4)
      .map((line) => labeledNote(line));
  }

  if (specs.chips.length === 0) {
    const line = mentionLines(source, /\bbadges?\b|\bchips?\b|\bpills?\b/i).find((entry) =>
      /\bpill|\bchip|\bround\b/i.test(entry),
    );
    if (line) {
      const list = line.includes(":") ? (line.split(":").pop() ?? line) : line;
      specs.chips = list
        .split(/,| and /)
        .map((part) => sentence(part))
        .filter((part) => /badge|chip|pill|tag/i.test(part))
        .map((name) => ({ name, detail: "" }));
    }
  }

  if (specs.responsive.length === 0) {
    specs.responsive = mentionLines(source, /\bresponsive\b|\btouch targets?\b|\bbreakpoints?\b/i)
      .slice(0, 4)
      .map((line) => labeledNote(line));
  }
}

function mentionLines(source: string, pattern: RegExp): string[] {
  const found: string[] = [];
  let fence = false;
  for (const line of source.replaceAll("\r\n", "\n").split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      fence = !fence;
      continue;
    }
    if (fence || trimmed.startsWith("#")) {
      continue;
    }
    const stripped = plain(trimmed.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, ""))
      .replace(/^don'?t\b|^do not\b|^do\b/i, "")
      .trim();
    const text = /^\w+\s*\(/.test(stripped) ? stripped : sentence(stripped);
    if (text && pattern.test(text) && text.length <= 160) {
      found.push(text);
    }
  }
  return found;
}

function labeledNote(line: string): SpecNote {
  const labeled = /^([^:]{2,48}):\s+(.+)$/.exec(line);
  if (!labeled) {
    return { name: line, detail: "" };
  }
  return { name: labeled[1]?.trim() ?? line, detail: labeled[2]?.trim() ?? "" };
}

export function shadowPreview(detail: string, colors: ColorToken[]): string | null {
  const match =
    /(-?\d+(?:\.\d+)?)\s*(?:r?px)?\s+(-?\d+(?:\.\d+)?)\s*(?:r?px)?\s+(-?\d+(?:\.\d+)?)\s*(?:r?px)?(?:\s+(-?\d+(?:\.\d+)?)\s*(?:r?px)?)?\s+([a-z][a-z-]*)\s+at\s+(\d+(?:\.\d+)?)%/i.exec(
      detail,
    );
  if (!match) {
    return null;
  }
  const spread = match[4] ? ` ${match[4]}px` : "";
  const alpha = Number(match[6]) / 100;
  return `${match[1]}px ${match[2]}px ${match[3]}px${spread} rgba(${rgbFor(match[5] ?? "", colors)}, ${alpha})`;
}

export function buttonTone(note: SpecNote): { background: string; color: string } {
  const text = `${note.name} ${note.detail}`.toLowerCase();
  if (/coral/.test(text) && /teal/.test(text)) {
    return { background: "#2a2a2e", color: "#ffffff" };
  }
  if (/gold|accent/.test(text)) {
    return { background: "#ffd23f", color: "#1a1a1d" };
  }
  if (/coral|boom|danger|error/.test(text)) {
    return { background: "#ef6c4a", color: "#ffffff" };
  }
  if (/sky|info/.test(text)) {
    return { background: "#5dade2", color: "#0c0c0e" };
  }
  if (/teal|primary/.test(text)) {
    return { background: "#2ba8a2", color: "#ffffff" };
  }
  if (/ghost|secondary|white/.test(text)) {
    return { background: "#ffffff", color: "#1a1a1d" };
  }
  return { background: "#2a2a2e", color: "#ffffff" };
}

export function accentFor(note: SpecNote): string {
  const text = `${note.name} ${note.detail}`.toLowerCase();
  if (/gold|accent|highlight/.test(text)) {
    return "#ffd23f";
  }
  if (/coral|boom|danger/.test(text)) {
    return "#ef6c4a";
  }
  if (/sky/.test(text)) {
    return "#5dade2";
  }
  if (/teal|default|primary/.test(text)) {
    return "#3cc4bd";
  }
  return "#4a4a50";
}

export function shortLabel(name: string): string {
  const label = name
    .replace(/\s*\([^)]*\)\s*/g, " ")
    .replace(/\bbuttons?\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  return label || name;
}

function collect(block: Block, specs: GuideSpecs): void {
  const kind = classify(block.title);
  if (kind === "cards" || kind === "inputs" || kind === "buttons") {
    const group = specs[kind];
    if (!group.summary) {
      group.summary = clip(intro(block.lines), 160);
    }
    const items = block.children.length > 0 ? childNotes(block) : specLines(block.lines);
    group.items.push(...items.slice(0, 6));
    return;
  }
  if (kind === "components") {
    specs.components.push(...componentNotes(block));
    for (const child of block.children) {
      collect(child, specs);
    }
    return;
  }
  if (kind === "chips") {
    specs.chips.push(...(block.children.length > 0 ? childNotes(block) : specLines(block.lines)));
    return;
  }
  if (kind === "elevation") {
    specs.elevation.push(...specLines(block.lines));
    return;
  }
  if (kind === "rules") {
    const rules = splitRules(block.lines);
    specs.dos.push(...rules.dos);
    specs.donts.push(...rules.donts);
    return;
  }
  if (kind === "responsive") {
    const items = block.children.length > 0 ? childNotes(block) : specLines(block.lines);
    specs.responsive.push(...items);
    return;
  }

  for (const child of block.children) {
    collect(child, specs);
  }
}

function classify(title: string): SpecKind | null {
  const text = bareTitle(title).toLowerCase();
  if (/\bdo'?s?\b/.test(text) && /\bdon'?t/.test(text)) {
    return "rules";
  }
  if (/\bresponsive\b|\bbreakpoints?\b/.test(text)) {
    return "responsive";
  }
  if (/\belevation\b|\bshadows?\b|\bdepth\b/.test(text)) {
    return "elevation";
  }
  if (/^chips?\b|^badges?\b|^tags?\b/.test(text)) {
    return "chips";
  }
  if (/^cards?\b/.test(text)) {
    return "cards";
  }
  if (/^inputs?\b|^fields?\b/.test(text)) {
    return "inputs";
  }
  if (/^buttons?\b/.test(text)) {
    return "buttons";
  }
  if (/^components?\b|^component library\b/.test(text)) {
    return "components";
  }
  return null;
}

function componentNotes(block: Block): SpecNote[] {
  if (block.children.length === 0) {
    return specLines(block.lines);
  }
  return block.children.flatMap((child) => {
    const bullets = specLines(child.lines).filter((note) => note.name.length <= 32);
    const listed = bullets.length > 0 && bullets.every((note) => note.detail.length === 0);
    if (listed) {
      return bullets.map((note) => ({ name: note.name, detail: bareTitle(child.title) }));
    }
    return [{ name: bareTitle(child.title), detail: clip(childDetail(child), 90) }];
  });
}

function childNotes(block: Block): SpecNote[] {
  return block.children.map((child) => ({
    name: bareTitle(child.title),
    detail: clip(childDetail(child), 140),
  }));
}

function childDetail(block: Block): string {
  const lead = intro(block.lines);
  const notes = specLines(block.lines).map((note) =>
    note.detail ? `${note.name}: ${note.detail}` : note.name,
  );
  return [lead, ...notes].filter((part) => part.length > 0).join(". ");
}

function specLines(lines: string[]): SpecNote[] {
  const notes: SpecNote[] = [];
  let fence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      fence = !fence;
      continue;
    }
    if (!trimmed || trimmed === "---" || trimmed.startsWith("#")) {
      continue;
    }
    const text = plain(trimmed.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, ""));
    if (!text || /^do(?:n't| not)?\b/i.test(text)) {
      continue;
    }
    const labeled = /^([^:]{2,48}):\s+(.+)$/.exec(text);
    if (labeled) {
      notes.push({ name: labeled[1]?.trim() ?? text, detail: labeled[2]?.trim() ?? "" });
      continue;
    }
    const spaced = /^(.{2,28}?)\s{2,}(.+)$/.exec(text);
    if (spaced) {
      notes.push({ name: spaced[1]?.trim() ?? text, detail: spaced[2]?.trim() ?? "" });
      continue;
    }
    if (fence || /^[-*]/.test(trimmed)) {
      notes.push({ name: text, detail: "" });
    }
  }
  return notes;
}

function splitRules(lines: string[]): { dos: string[]; donts: string[] } {
  const dos: string[] = [];
  const donts: string[] = [];
  for (const line of lines) {
    const text = plain(
      line
        .trim()
        .replace(/^[-*]\s+/, "")
        .replace(/^\d+\.\s+/, ""),
    );
    if (!text) {
      continue;
    }
    if (/^don'?t\b|^do not\b/i.test(text)) {
      donts.push(sentence(text.replace(/^don'?t\b|^do not\b/i, "")));
      continue;
    }
    if (/^do\b/i.test(text)) {
      dos.push(sentence(text.replace(/^do\b/i, "")));
    }
  }
  return { dos, donts };
}

function intro(lines: string[]): string {
  const parts: string[] = [];
  let fence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (parts.length > 0) {
        break;
      }
      fence = !fence;
      continue;
    }
    if (fence) {
      continue;
    }
    if (
      !trimmed ||
      trimmed === "---" ||
      /^[-*]/.test(trimmed) ||
      /^\d+\./.test(trimmed) ||
      trimmed.startsWith("|")
    ) {
      if (parts.length > 0) {
        break;
      }
      continue;
    }
    parts.push(plain(trimmed));
  }
  return parts.join(" ");
}

function parseBlocks(source: string): Block[] {
  const root: Block[] = [];
  const stack: Block[] = [];
  let fence = false;

  for (const line of source.replaceAll("\r\n", "\n").split("\n")) {
    if (!fence && /^(#{1,4})\s+(.+)$/.test(line.trim())) {
      const heading = /^(#{1,4})\s+(.+)$/.exec(line.trim());
      const block: Block = {
        level: heading?.[1]?.length ?? 1,
        title: heading?.[2]?.trim() ?? "",
        lines: [],
        children: [],
      };
      while (stack.length > 0 && (stack[stack.length - 1]?.level ?? 0) >= block.level) {
        stack.pop();
      }
      const parent = stack[stack.length - 1];
      if (parent) {
        parent.children.push(block);
      } else {
        root.push(block);
      }
      stack.push(block);
      continue;
    }
    if (line.trim().startsWith("```")) {
      fence = !fence;
    }
    stack[stack.length - 1]?.lines.push(line);
  }

  return root;
}

function bareTitle(title: string): string {
  return title.replace(/^\d+\.\s*/, "").trim();
}

function plain(value: string): string {
  return value.replaceAll("**", "").replaceAll("`", "").replace(/\s+/g, " ").trim();
}

function clip(value: string, max: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

function sentence(value: string): string {
  const text = value.replace(/^[\s,.:;-]+/, "").trim();
  if (!text) {
    return "";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function emptyGroup(): SpecGroup {
  return { summary: "", items: [] };
}

function rgbFor(word: string, colors: ColorToken[]): string {
  const key = word.toLowerCase();
  if (key === "black") {
    return "0, 0, 0";
  }
  if (key === "white") {
    return "255, 255, 255";
  }
  const aliases: Record<string, RegExp> = {
    teal: /teal/i,
    coral: /^coral$/i,
    gold: /gold/i,
    sky: /sky/i,
    "sky-blue": /sky/i,
    primary: /primary teal|^primary$/i,
    accent: /accent gold|^accent$/i,
  };
  const pattern = aliases[key] ?? new RegExp(key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
  const found = colors.find((color) => pattern.test(color.name));
  return found ? hexToRgb(found.hex) : "255, 255, 255";
}

function hexToRgb(hex: string): string {
  const body = hex.replace("#", "");
  const red = Number.parseInt(body.slice(0, 2), 16);
  const green = Number.parseInt(body.slice(2, 4), 16);
  const blue = Number.parseInt(body.slice(4, 6), 16);
  return `${red}, ${green}, ${blue}`;
}
