"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortValue?: (row: T) => number | string;
  align?: "left" | "right" | "center";
  mono?: boolean;
  width?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  dense = false,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  dense?: boolean;
  className?: string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const sorted = sort
    ? [...rows].sort((a, b) => {
        const col = columns.find((c) => c.key === sort.key);
        if (!col?.sortValue) return 0;
        const av = col.sortValue(a);
        const bv = col.sortValue(b);
        if (av < bv) return -1 * sort.dir;
        if (av > bv) return 1 * sort.dir;
        return 0;
      })
    : rows;

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: -1 };
      if (prev.dir === -1) return { key, dir: 1 };
      return null;
    });
  }

  const cellPad = dense ? "px-3 py-1.5" : "px-3 py-2.5";

  return (
    <div className={cn("overflow-x-auto border border-rule", className)}>
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-rule bg-paper-2">
            {columns.map((col) => {
              const active = sort?.key === col.key;
              return (
                <th
                  key={col.key}
                  style={{ width: col.width }}
                  aria-sort={col.sortValue ? (active ? (sort!.dir === 1 ? "ascending" : "descending") : "none") : undefined}
                  className={cn(
                    "font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3",
                    cellPad,
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  )}
                >
                  {col.sortValue ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className={cn(
                        "inline-flex items-center gap-1 hover:text-ink",
                        col.align === "right" && "flex-row-reverse"
                      )}
                    >
                      {col.header}
                      {active ? (
                        sort!.dir === -1 ? <ArrowDown size={11} /> : <ArrowUp size={11} />
                      ) : (
                        <ChevronsUpDown size={11} className="opacity-40" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                "border-b border-rule last:border-b-0",
                onRowClick && "cursor-pointer hover:bg-paper-2"
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    cellPad,
                    "text-small text-ink-2",
                    col.mono && "font-mono font-tnum",
                    col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                  )}
                >
                  {col.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-small text-ink-3">
                No rows.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
