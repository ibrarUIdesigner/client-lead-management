import { useState } from "react";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { useApifyItems, useImportApifyItems } from "../../hooks/useApify";
import { apiErrorMessage } from "../../lib/apiError";
import { formatWhen } from "../../lib/format";
import type { ApifyRun } from "../../types/apify";
import { TERMINAL_RUN_STATUSES } from "../../types/apify";

const PAGE_SIZE = 25;

type ResultsPanelProps = {
  run: ApifyRun;
  onImported: (message: string) => void;
};

export function ResultsPanel({ run, onImported }: ResultsPanelProps) {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const ready = TERMINAL_RUN_STATUSES.has(run.status);
  const items = useApifyItems(run.id, offset, ready);
  const importItems = useImportApifyItems();

  if (!ready) {
    return (
      <EmptyState
        compact
        title="Results are not ready"
        description="Records show up here after the run succeeds, fails, times out, or is aborted."
      />
    );
  }

  const page = items.data;
  const pageKeys = page?.items.map((item) => item.item_key) ?? [];
  const allSelected = pageKeys.length > 0 && pageKeys.every((key) => selected.has(key));

  function togglePage(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const key of pageKeys) {
        if (checked) {
          next.add(key);
        } else {
          next.delete(key);
        }
      }
      return next;
    });
  }

  async function onImport() {
    if (importing || selected.size === 0) {
      return;
    }
    setImporting(true);
    setImportError(null);
    try {
      const result = await importItems.mutateAsync({
        runId: run.id,
        itemKeys: [...selected],
      });
      setSelected(new Set());
      const skipped =
        result.skipped === 1
          ? "1 record was already saved."
          : `${result.skipped} records were already saved.`;
      onImported(
        result.created === 0
          ? `No new leads. ${skipped}`
          : `Imported ${result.created} ${result.created === 1 ? "lead" : "leads"}. ${skipped}`,
      );
    } catch (caught) {
      setImportError(apiErrorMessage(caught, "Those records could not be imported."));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-4">
      <QueryGate
        pending={items.isPending}
        error={items.error}
        fallback="Results could not be loaded."
        onRetry={() => {
          void items.refetch();
        }}
      >
        {page && page.items.length === 0 ? (
          <EmptyState
            compact
            title="No records"
            description="This run did not save any dataset records."
          />
        ) : page ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Checkbox
                label={`Select this page (${page.total} total)`}
                checked={allSelected}
                onChange={(event) => {
                  togglePage(event.target.checked);
                }}
              />
              <Button
                isLoading={importing}
                disabled={selected.size === 0}
                onClick={() => void onImport()}
              >
                Import to Leads
              </Button>
            </div>
            <p className="text-small text-gray-500">
              Selected records are saved as leads. Nothing is emailed.
            </p>
            {importError ? (
              <p className="text-small text-danger" role="alert">
                {importError}
              </p>
            ) : null}
            <div className="overflow-x-auto rounded-card border border-gray-200">
              <table className="w-full min-w-[640px] text-left text-body">
                <thead className="bg-gray-50 text-small text-gray-600">
                  <tr>
                    <th className="px-4 py-3 font-medium" scope="col">
                      Select
                    </th>
                    <th className="px-4 py-3 font-medium" scope="col">
                      Record
                    </th>
                    <th className="px-4 py-3 font-medium" scope="col">
                      Source URL
                    </th>
                    <th className="px-4 py-3 font-medium" scope="col">
                      Collected
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((item) => (
                    <tr key={item.item_key} className="border-t border-gray-200">
                      <td className="px-4 py-3 align-top">
                        <label className="inline-flex min-h-11 items-center">
                          <span className="sr-only">Select {item.title}</span>
                          <input
                            type="checkbox"
                            className="size-4 accent-primary"
                            checked={selected.has(item.item_key)}
                            onChange={(event) => {
                              setSelected((current) => {
                                const next = new Set(current);
                                if (event.target.checked) {
                                  next.add(item.item_key);
                                } else {
                                  next.delete(item.item_key);
                                }
                                return next;
                              });
                            }}
                          />
                        </label>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <p className="font-medium text-ink">{item.title}</p>
                        {item.detail ? (
                          <p className="mt-1 text-small text-gray-600">{item.detail}</p>
                        ) : null}
                        {item.fields.length > 0 ? (
                          <dl className="mt-2 space-y-1">
                            {item.fields.map((field) => (
                              <div key={field.label} className="text-small text-gray-600">
                                <dt className="inline font-medium">{field.label}: </dt>
                                <dd className="inline">{field.value}</dd>
                              </div>
                            ))}
                          </dl>
                        ) : null}
                      </td>
                      <td className="max-w-xs px-4 py-3 align-top break-all text-small text-gray-700">
                        {item.source_url ?? "—"}
                      </td>
                      <td className="px-4 py-3 align-top text-small text-gray-700">
                        {formatWhen(item.collected_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="secondary"
                disabled={offset === 0}
                onClick={() => {
                  setOffset((current) => Math.max(0, current - PAGE_SIZE));
                }}
              >
                Previous
              </Button>
              <p className="text-small text-gray-600">
                {page.total === 0
                  ? "0 records"
                  : `${offset + 1}–${offset + page.items.length} of ${page.total}`}
              </p>
              <Button
                variant="secondary"
                disabled={!page.has_next}
                onClick={() => {
                  setOffset((current) => current + PAGE_SIZE);
                }}
              >
                Next
              </Button>
            </div>
          </>
        ) : null}
      </QueryGate>
    </div>
  );
}
