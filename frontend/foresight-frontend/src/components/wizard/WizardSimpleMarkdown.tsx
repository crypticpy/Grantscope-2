import React from "react";

/**
 * Renders inline formatting: **bold** and *italic*.
 */
function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      parts.push(
        <strong key={match.index} className="font-semibold">
          {match[2]}
        </strong>,
      );
    } else if (match[3]) {
      parts.push(<em key={match.index}>{match[3]}</em>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

/**
 * Lightweight markdown for wizard interview bubbles.
 * Supports headings, bullet/numbered lists, paragraphs, bold, and italics.
 */
export function WizardSimpleMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul
          key={`list-${elements.length}`}
          className="list-disc list-inside space-y-1 my-2"
        >
          {listItems.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      listItems.push(trimmed.replace(/^\d+\.\s/, ""));
      continue;
    }

    flushList();

    if (!trimmed) {
      elements.push(<br key={`br-${i}`} />);
      continue;
    }

    if (trimmed.startsWith("### ")) {
      elements.push(
        <p key={`h3-${i}`} className="font-semibold mt-3 mb-1">
          {renderInline(trimmed.slice(4))}
        </p>,
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <p key={`h2-${i}`} className="font-bold mt-3 mb-1">
          {renderInline(trimmed.slice(3))}
        </p>,
      );
      continue;
    }

    elements.push(
      <p key={`p-${i}`} className="my-1">
        {renderInline(trimmed)}
      </p>,
    );
  }

  flushList();

  return <div className="text-sm leading-relaxed">{elements}</div>;
}

export default WizardSimpleMarkdown;

