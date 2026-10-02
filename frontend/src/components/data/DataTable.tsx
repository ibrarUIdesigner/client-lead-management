import type { ReactNode } from "react";

import { useOnline } from "../../hooks/useOnline";
import { EmptyState } from "../feedback/EmptyState";
import { LoadingState } from "../feedback/LoadingState";
import { OfflineState } from "../feedback/OfflineState";
import { Button } from "../ui/Button";
import { cn } from "../../lib/cn";
import { Pagination } from "./Pagination";

export type DataColumn<T> = {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
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
  renderCard?: (row: T) => ReactNode;
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
  renderCard,
  page,
  pageCount,
  onPageChange,
}: DataTableProps<T>) {
  const online = useOnline();
  const showOffline = !online && (isLoading || Boolean(error) || rows.length === 0);
  const showRows = !showOffline && !isLoading && !error && rows.length > 0;

  return (
    <div className="overflow-hidden rounded-card border border-gray-200 bg-white">
      {showOffline ? (
        <div className="p-4 sm:p-6">
          <OfflineState onRetry={onRetry} />
        </div>
      ) : null}

      {!showOffline && isLoading ? (
        <div className="p-4 sm:p-6">
          <LoadingState label="Loading records" framed={false} />
        </div>
      ) : null}

      {!showOffline && !isLoading && error ? (
        <div className="flex flex-col items-start gap-3 p-4 sm:p-6" role="alert">
          <h2 className="text-h4 font-semibold text-ink">Could not load this</h2>
          <p className="text-body text-danger">{error}</p>
          {onRetry ? (
            <Button variant="secondary" onClick={onRetry}>
              Try again
            </Button>
          ) : null}
        </div>
      ) : null}

      {!showOffline && !isLoading && !error && rows.length === 0 ? (
        <div className="p-4 sm:p-6">
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
        </div>
      ) : null}

      {showRows ? (
        <>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-max min-w-full border-collapse text-left">
              <thead className="bg-gray-50">
                <tr>
                  {columns.map((column) => (
                    <th
                      key={column.id}
                      scope="col"
                      className={cn(
                        "px-4 py-3 text-caption font-semibold whitespace-nowrap text-gray-500",
                        column.className,
                      )}
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
                      <td
                        key={column.id}
                        className={cn(
                          "min-h-16 px-4 py-2 align-middle text-body text-ink",
                          column.className,
                        )}
                      >
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
              <li key={getRowId(row)} className="px-4 py-4">
                {renderCard ? (
                  renderCard(row)
                ) : (
                  <div className="space-y-2">
                    {columns.map((column) => (
                      <div key={column.id}>
                        <p className="text-caption font-semibold text-gray-500">{column.header}</p>
                        <div className="mt-1 text-body break-words text-ink">{column.cell(row)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {page !== undefined &&
      pageCount !== undefined &&
      onPageChange &&
      showRows ? (
        <div className="border-t border-gray-200 px-4 py-3">
          <Pagination page={page} pageCount={pageCount} onPageChange={onPageChange} />
        </div>
      ) : null}
    </div>
  );
}
