import type { ReactNode } from "react";

import {
  accentFor,
  buttonTone,
  extractGuideSpecs,
  hasGuideSpecs,
  shadowPreview,
  shortLabel,
  type GuideSpecs,
  type SpecNote,
} from "./specs";
import { extractDesignTokens, hasDesignTokens, type DesignTokens } from "./tokens";

type DesignTokenRailProps = {
  name: string;
  description?: string | null;
  source: string;
};

export function DesignTokenRail({ name, description, source }: DesignTokenRailProps) {
  const tokens = extractDesignTokens(source);
  const specs = extractGuideSpecs(source);
  if (!hasDesignTokens(tokens) && !hasGuideSpecs(specs)) {
    return null;
  }

  const summary = description?.trim() || tokens.summary;
  const columns = Math.min(Math.max(tokens.colors.length, 1), 8);
  const largestRadius = Math.max(
    ...tokens.radii.filter((token) => !token.full).map((token) => token.px),
    1,
  );
  const largestSpace = Math.max(...tokens.spacing.map((token) => token.px), 1);
  const splitScale = tokens.radii.length > 0 && tokens.spacing.length > 0;

  return (
    <aside
      aria-label="Design tokens"
      className="rounded-2xl border border-gray-200 bg-white p-4 text-ink xl:sticky xl:top-24 xl:max-h-[calc(100dvh-7.5rem)] xl:overflow-y-auto"
    >
      <h2 className="text-[15px] leading-5 font-semibold tracking-tight">{name}</h2>
      {summary ? (
        <p className="mt-1.5 line-clamp-3 text-[12px] leading-[1.45] text-gray-600">{summary}</p>
      ) : null}

      {tokens.colors.length > 0 ? (
        <TokenSection title="Palette">
          <div
            className="grid gap-1"
            style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
          >
            {tokens.colors.map((color) => (
              <div
                key={`${color.name}-${color.hex}`}
                title={`${color.name} ${color.hex.toUpperCase()}`}
                className="h-8 rounded-md shadow-[inset_0_0_0_1px_rgba(0,0,0,0.12)]"
                style={{ backgroundColor: color.hex }}
              >
                <span className="sr-only">
                  {color.name} {color.hex}
                </span>
              </div>
            ))}
          </div>
        </TokenSection>
      ) : null}

      {tokens.type.length > 0 ? (
        <TokenSection title="Typography">
          <div className="grid grid-cols-3 gap-2">
            {tokens.type.map((token) => (
              <TypeCard key={token.name} token={token} />
            ))}
          </div>
        </TokenSection>
      ) : null}

      {splitScale ? (
        <div className="mt-5 grid grid-cols-2 items-start gap-4">
          <RadiusBlock tokens={tokens.radii} largest={largestRadius} />
          <SpacingBlock tokens={tokens.spacing} largest={largestSpace} />
        </div>
      ) : (
        <>
          {tokens.radii.length > 0 ? (
            <div className="mt-5">
              <RadiusBlock tokens={tokens.radii} largest={largestRadius} />
            </div>
          ) : null}
          {tokens.spacing.length > 0 ? (
            <div className="mt-5">
              <SpacingBlock tokens={tokens.spacing} largest={largestSpace} />
            </div>
          ) : null}
        </>
      )}

      <SpecGroupView title="Cards" group={specs.cards} variant="cards" />
      <SpecGroupView title="Inputs" group={specs.inputs} variant="inputs" />
      <SpecGroupView title="Buttons" group={specs.buttons} variant="buttons" />
      <NoteList title="Components" notes={specs.components} variant="pills" />
      <NoteList title="Chips" notes={specs.chips} variant="chips" />
      <ElevationList notes={specs.elevation} colors={tokens.colors} />
      <RulesList dos={specs.dos} donts={specs.donts} />
      <NoteList title="Responsive Behavior" notes={specs.responsive} variant="rows" />
    </aside>
  );
}

function TokenSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 text-[13px] font-medium text-ink">{title}</h3>
      {children}
    </section>
  );
}

function TypeCard({ token }: { token: DesignTokens["type"][number] }) {
  const meta = token.weight === null ? token.size : `${token.size} · w${token.weight}`;
  return (
    <div className="min-w-0 rounded-lg bg-gray-50 px-2.5 py-2.5">
      <p className="text-[22px] leading-none text-ink" style={{ fontWeight: token.weight ?? 500 }}>
        Aa
      </p>
      <p className="mt-2 truncate text-[11px] text-gray-600" title={token.name}>
        {token.name}
      </p>
      <p className="mt-0.5 truncate text-[11px] text-gray-500">{meta}</p>
    </div>
  );
}

function RadiusBlock({ tokens, largest }: { tokens: DesignTokens["radii"]; largest: number }) {
  return (
    <section>
      <h3 className="mb-2 text-[13px] font-medium text-ink">Radius</h3>
      <div className="flex flex-wrap gap-x-2.5 gap-y-2">
        {tokens.map((token) => (
          <div key={token.name} className="flex w-8 flex-col items-center gap-1">
            <div
              className="size-7 bg-gray-300"
              style={{ borderRadius: radiusPreview(token, largest) }}
              title={token.full ? token.name : `${token.name} ${token.px}`}
            />
            <span className="max-w-full truncate text-[10px] text-gray-500">{token.name}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function radiusPreview(token: DesignTokens["radii"][number], largest: number): number {
  if (token.full) {
    return 999;
  }
  if (token.px === 0) {
    return 0;
  }
  return Math.min(10, Math.max(2, (token.px / largest) * 10));
}

function SpacingBlock({ tokens, largest }: { tokens: DesignTokens["spacing"]; largest: number }) {
  return (
    <section>
      <h3 className="mb-2 text-[13px] font-medium text-ink">Spacing</h3>
      <ul className="space-y-1.5">
        {tokens.map((token) => (
          <li key={token.name} className="grid grid-cols-[2.4rem_minmax(0,1fr)] items-center gap-2">
            <span className="truncate text-[11px] text-gray-500" title={token.name}>
              {token.name}
            </span>
            <span className="block h-2 overflow-hidden">
              <span
                className="block h-2 rounded-full bg-[#8fbf3f]"
                style={{ width: `${Math.max(14, Math.round((token.px / largest) * 100))}%` }}
                title={`${token.name} ${token.px}`}
              />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SpecGroupView({
  title,
  group,
  variant,
}: {
  title: string;
  group: GuideSpecs["cards"];
  variant: "cards" | "inputs" | "buttons";
}) {
  if (group.items.length === 0 && !group.summary) {
    return null;
  }

  return (
    <TokenSection title={title}>
      {group.summary ? (
        <p className="mb-2 line-clamp-2 text-[11px] leading-snug text-gray-600">{group.summary}</p>
      ) : null}
      {variant === "buttons" ? (
        <div className="flex flex-wrap gap-1.5">
          {group.items.map((item) => {
            const tone = buttonTone(item);
            return (
              <span
                key={item.name}
                title={item.detail || item.name}
                className="rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-black/10"
                style={{ background: tone.background, color: tone.color }}
              >
                {shortLabel(item.name)}
              </span>
            );
          })}
        </div>
      ) : null}
      {variant === "inputs" ? (
        <div className="mb-2 rounded-md border border-black/10 bg-[#fff8e7] px-2.5 py-1.5 text-[11px] text-[#1e8c86]">
          Input
        </div>
      ) : null}
      {variant === "cards" ? (
        <ul className="space-y-1.5">
          {group.items.map((item) => (
            <li key={item.name} className="flex overflow-hidden rounded-md bg-gray-50">
              <span className="w-1 shrink-0" style={{ background: accentFor(item) }} />
              <span className="min-w-0 px-2 py-1.5">
                <span className="block truncate text-[11px] font-medium text-ink">{item.name}</span>
                {item.detail ? (
                  <span className="block truncate text-[10px] text-gray-500">{item.detail}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : variant === "inputs" ? (
        <NoteRows notes={group.items} />
      ) : null}
    </TokenSection>
  );
}

function NoteList({
  title,
  notes,
  variant,
}: {
  title: string;
  notes: SpecNote[];
  variant: "pills" | "chips" | "rows";
}) {
  if (notes.length === 0) {
    return null;
  }

  return (
    <TokenSection title={title}>
      {variant === "rows" ? (
        <NoteRows notes={notes} />
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {notes.map((note) => (
            <span
              key={`${note.name}-${note.detail}`}
              title={note.detail || note.name}
              className={
                variant === "chips"
                  ? "rounded-full bg-gray-100 px-2.5 py-1 text-[11px] text-gray-700"
                  : "rounded-md bg-gray-100 px-2 py-1 text-[11px] text-gray-700"
              }
            >
              {compactName(note.name)}
            </span>
          ))}
        </div>
      )}
    </TokenSection>
  );
}

function compactName(name: string): string {
  return (
    name
      .replace(/\s*\([^)]*\)\s*/g, " ")
      .replace(/\s+/g, " ")
      .trim() || name
  );
}

function NoteRows({ notes }: { notes: SpecNote[] }) {
  return (
    <ul className="space-y-1.5">
      {notes.map((note) => (
        <li key={`${note.name}-${note.detail}`} className="min-w-0">
          <p className="truncate text-[11px] font-medium text-ink" title={note.name}>
            {note.name}
          </p>
          {note.detail ? (
            <p className="line-clamp-2 text-[10px] leading-snug text-gray-500">{note.detail}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function ElevationList({ notes, colors }: { notes: SpecNote[]; colors: DesignTokens["colors"] }) {
  if (notes.length === 0) {
    return null;
  }

  return (
    <TokenSection title="Elevation & Depth">
      <ul className="space-y-2">
        {notes.map((note) => (
          <li key={note.name} className="flex items-center gap-2">
            <span
              className="size-7 shrink-0 rounded-md border border-gray-200 bg-white"
              style={{ boxShadow: shadowPreview(note.detail, colors) ?? "none" }}
            />
            <span className="min-w-0">
              <span className="block truncate text-[11px] text-ink">{note.name}</span>
              {note.detail ? (
                <span className="block truncate text-[10px] text-gray-500">{note.detail}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </TokenSection>
  );
}

function RulesList({ dos, donts }: { dos: string[]; donts: string[] }) {
  if (dos.length === 0 && donts.length === 0) {
    return null;
  }

  return (
    <TokenSection title="Do's & Don'ts">
      <div className="space-y-3">
        {dos.length > 0 ? <RuleColumn label="Do" items={dos} tone="do" /> : null}
        {donts.length > 0 ? <RuleColumn label="Don't" items={donts} tone="dont" /> : null}
      </div>
    </TokenSection>
  );
}

function RuleColumn({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone: "do" | "dont";
}) {
  return (
    <div>
      <p
        className={
          tone === "do"
            ? "text-[11px] font-medium text-[#3f7a16]"
            : "text-[11px] font-medium text-[#d45233]"
        }
      >
        {label}
      </p>
      <ul className="mt-1 space-y-1">
        {items.map((item) => (
          <li key={item} className="text-[11px] leading-snug text-gray-600">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
