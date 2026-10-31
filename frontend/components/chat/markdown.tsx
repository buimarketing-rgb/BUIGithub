"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "@/types";

/** Renders answer markdown; [n] citations become clickable chips linked to the source list. */
export function Markdown({ content, sources, onCite }: { content: string; sources?: Source[]; onCite?: (n: number) => void }) {
  const withCites = content.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");
  return (
    <div className="prose-bui break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-")) {
              const n = Number(href.slice(6));
              const s = sources?.find((x) => x.n === n);
              return (
                <button type="button" onClick={() => onCite?.(n)} title={s ? `${s.title}${s.section ? " — " + s.section : ""}` : `Source ${n}`}
                  className={`mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded px-1 align-text-top text-[10px] font-semibold no-underline ${s && !s.verified ? "bg-warning/15 text-warning" : "bg-primary/12 text-primary"} hover:bg-primary hover:text-primary-foreground`}>
                  {n}
                </button>
              );
            }
            const safe = href && /^(https?:|mailto:|\/)/.test(href) ? href : undefined;
            return <a href={safe} target="_blank" rel="noopener noreferrer nofollow">{children}</a>;
          },
          img: () => null, // never load remote images from model output
        }}>
        {withCites}
      </ReactMarkdown>
    </div>
  );
}
