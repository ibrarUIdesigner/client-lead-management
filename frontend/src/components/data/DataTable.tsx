import type { ReactNode } from "react";

import { EmptyState } from "../feedback/EmptyState";
import { Button } from "../ui/Button";
import { Skeleton } from "../ui/Skeleton";
import { Pagination } from "./Pagination";

export type DataColumn<T> = {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataColumn<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  page?: number;
  pageCount?: number;
  onPageChange?: (page: number) => void;
};

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  isLoading = false,
  error = null,
  onRetry,
  emptyTitle = "Nothing here yet",
  emptyDescription = "Records will show up here.",
  emptyAction,
  page,
  pageCount,
  onPageChange,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-card border border-gray-200 bg-white">
      {isLoading ? (
        <div className="space-y-3 p-6" aria-busy="true" aria-live="polite">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="flex flex-col items-start gap-3 p-6" role="alert">
          <p className="text-body text-danger">{error}</p>
          {onRetry ? (
            <Button variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}

      {!isLoading && !error && rows.length === 0 ? (
        <div className="p-6">
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
        </div>
      ) : null}

      {!isLoading && !error && rows.length > 0 ? (
        <>
          <div className="hidden md:block">
            <table className="w-full border-collapse text-left">
              <thead className="bg-gray-50">
                <tr>
                  {columns.map((column) => (
                    <th
                      key={column.id}
                      scope="col"
                      className="px-4 py-3 text-caption font-semibold text-gray-500"
                    >
                      {column.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={getRowId(row)} className="border-t border-gray-200 hover:bg-gray-50">
                    {columns.map((column) => (
                      <td key={column.id} className="h-16 px-4 text-body text-ink">
                        {column.cell(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="divide-y divide-gray-200 md:hidden">
            {rows.map((row) => (
              <li key={getRowId(row)} className="space-y-2 px-4 py-4">
                {columns.map((column) => (
                  <div key={column.id}>
                    <p className="text-caption font-semibold text-gray-500">{column.header}</p>
                    <div className="mt-1 text-body text-ink">{column.cell(row)}</div>
                  </div>
                ))}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {page !== undefined &&
      pageCount !== undefined &&
      onPageChange &&
      !isLoading &&
      !error &&
      rows.length > 0 ? (
        <div className="border-t border-gray-200 px-4 py-3">
          <Pagination page={page} pageCount={pageCount} onPageChange={onPageChange} />
        </div>
      ) : null}
    </div>
  );
}
