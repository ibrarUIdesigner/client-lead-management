import type { ReactNode } from "react";

type Inline =
  | { type: "text" | "strong" | "code"; text: string }
  | { type: "link"; text: string; href: string };

type Block =
  | { type: "heading"; level: number; inlines: Inline[] }
  | { type: "paragraph"; inlines: Inline[] }
  | { type: "list"; items: Inline[][] }
  | { type: "code"; text: string };

const headingPattern = /^(#{1,3}) +(.+)$/;
const bulletPattern = /^[-*] +(.+)$/;
const linkPattern = /\[([^\]\n]+)\]\(([^)\s]+)\)/;

export function MarkdownView({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  if (blocks.length === 0) {
    return <p className="text-body text-gray-500">Nothing to preview yet.</p>;
  }

  return (
    <div className="space-y-3 text-body text-ink">
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} />
      ))}
    </div>
  );
}

function BlockView({ block }: { block: Block }) {
  if (block.type === "heading") {
    const className =
      block.level === 1 ? "text-h3 font-semibold" : "text-h4 font-semibold";
    return <p className={className}>{renderInlines(block.inlines)}</p>;
  }
  if (block.type === "list") {
    return (
      <ul className="list-disc space-y-1 pl-5">
        {block.items.map((item, index) => (
          <li key={index}>{renderInlines(item)}</li>
        ))}
      </ul>
    );
  }
  if (block.type === "code") {
    return (
      <pre className="overflow-x-auto rounded-control bg-gray-50 p-3 text-small text-ink">
        <code>{block.text}</code>
      </pre>
    );
  }
  return <p>{renderInlines(block.inlines)}</p>;
}

function renderInlines(nodes: Inline[]): ReactNode[] {
  return nodes.map((node, index) => {
    if (node.type === "strong") {
      return <strong key={index}>{node.text}</strong>;
    }
    if (node.type === "code") {
      return (
        <code key={index} className="rounded bg-gray-100 px-1">
          {node.text}
        </code>
      );
    }
    if (node.type === "link") {
      return (
        <a
          key={index}
          href={node.href}
          className="text-primary-700 underline"
          rel="noreferrer"
          target="_blank"
        >
          {node.text}
        </a>
      );
    }
    return <span key={index}>{node.text}</span>;
  });
}

function parseMarkdown(source: string): Block[] {
  const lines = source.replaceAll("\r\n", "\n").replaceAll("\u0000", "").split("\n");
  const blocks: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index] ?? "";
    if (line.startsWith("```")) {
      index += 1;
      const code: string[] = [];
      while (index < lines.length && !(lines[index] ?? "").startsWith("```")) {
        code.push(lines[index] ?? "");
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push({ type: "code", text: code.join("\n") });
      continue;
    }
    const heading = headingPattern.exec(line);
    if (heading) {
      blocks.push({
        type: "heading",
        level: heading[1]?.length ?? 1,
        inlines: parseInlines(heading[2]?.trim() ?? ""),
      });
      index += 1;
      continue;
    }
    if (bulletPattern.test(line)) {
      const items: Inline[][] = [];
      while (index < lines.length && bulletPattern.test(lines[index] ?? "")) {
        const match = bulletPattern.exec(lines[index] ?? "");
        items.push(parseInlines(match?.[1] ?? ""));
        index += 1;
      }
      blocks.push({ type: "list", items });
      continue;
    }
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && (lines[index] ?? "").trim() && !startsBlock(lines[index] ?? "")) {
      paragraph.push((lines[index] ?? "").trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", inlines: parseInlines(paragraph.join(" ")) });
  }
  return blocks;
}

function parseInlines(text: string): Inline[] {
  const nodes: Inline[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    if (text.startsWith("**", cursor)) {
      const end = text.indexOf("**", cursor + 2);
      if (end !== -1) {
        nodes.push({ type: "strong", text: text.slice(cursor + 2, end) });
        cursor = end + 2;
        continue;
      }
    }
    if (text.startsWith("`", cursor)) {
      const end = text.indexOf("`", cursor + 1);
      if (end !== -1) {
        nodes.push({ type: "code", text: text.slice(cursor + 1, end) });
        cursor = end + 1;
        continue;
      }
    }
    const link = linkPattern.exec(text.slice(cursor));
    if (link && link.index === 0) {
      const href = link[2] ?? "";
      const label = link[1] ?? "";
      if (href.startsWith("https://") || href.startsWith("http://")) {
        nodes.push({ type: "link", text: label, href });
      } else {
        nodes.push({ type: "text", text: link[0] });
      }
      cursor += link[0].length;
      continue;
    }
    const next = nextMark(text, cursor + 1);
    nodes.push({ type: "text", text: text.slice(cursor, next) });
    cursor = next;
  }
  return nodes.filter((node) => node.text.length > 0);
}

function startsBlock(line: string): boolean {
  return headingPattern.test(line) || bulletPattern.test(line) || line.startsWith("```");
}

function nextMark(text: string, start: number): number {
  const marks = [text.length];
  for (const token of ["**", "`", "["]) {
    const found = text.indexOf(token, start);
    if (found !== -1) {
      marks.push(found);
    }
  }
  return Math.min(...marks);
}
