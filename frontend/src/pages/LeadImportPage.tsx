import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useImportLeads } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import type { LeadImportResult } from "../types/lead";

const template = "business_name,industry,city,country,website,email,phone,source,tags,notes\n";

export function LeadImportPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const importLeads = useImportLeads();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<LeadImportResult | null>(null);

  const downloadTemplate = () => {
    const blob = new Blob([template], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "leads-template.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const preview = () => {
    if (!file) {
      return;
    }
    importLeads.mutate(
      { file, dryRun: true },
      {
        onSuccess: (next) => {
          setResult(next);
        },
        onError: (error) => {
          setResult(null);
          notify(apiErrorMessage(error, "Could not read that file."), "danger");
        },
      },
    );
  };

  const confirm = () => {
    if (!file) {
      return;
    }
    importLeads.mutate(
      { file, dryRun: false },
      {
        onSuccess: (next) => {
          setResult(next);
          notify(
            next.created === 1 ? "Imported 1 lead." : `Imported ${next.created} leads.`,
            "success",
          );
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not import those leads."), "danger");
        },
      },
    );
  };

  return (
    <>
      <PageHeader
        title="Import leads"
        description="Valid rows are saved. Rows with a problem stay listed so you can fix them."
        actions={
          <Button variant="secondary" onClick={downloadTemplate}>
            Download template
          </Button>
        }
      />
      <Card>
        <p className="text-body text-gray-600">
          Include a header row. <span className="font-medium text-ink">business_name</span> is
          required. Optional columns are industry, city, country, website, email, phone, source,
          tags, and notes. Separate tags with commas or pipes.
        </p>
        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center">
          <label className="text-small font-medium text-gray-700">
            CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              className="mt-2 block w-full text-body"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setResult(null);
              }}
            />
          </label>
          <Button onClick={preview} isLoading={importLeads.isPending} disabled={!file}>
            Preview
          </Button>
        </div>
      </Card>

      {result ? (
        <div className="mt-6 space-y-6">
          <Card>
            <h2 className="text-h4 font-semibold text-ink">
              {result.valid_rows.length} {result.valid_rows.length === 1 ? "row is" : "rows are"}{" "}
              ready
            </h2>
            {result.valid_rows.length > 0 ? (
              <ul className="mt-4 divide-y divide-gray-200">
                {result.valid_rows.map((row) => (
                  <li key={row.row_number} className="py-3">
                    <p className="font-medium text-ink">{row.business_name}</p>
                    <p className="text-small text-gray-600">
                      Row {row.row_number}
                      {row.city ? ` · ${row.city}` : ""}
                      {row.email ? ` · ${row.email}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-body text-gray-600">
                Nothing in this file can be imported yet.
              </p>
            )}
            {result.dry_run ? (
              <div className="mt-4">
                <Button
                  onClick={confirm}
                  disabled={result.valid_rows.length === 0}
                  isLoading={importLeads.isPending}
                >
                  Import {result.valid_rows.length}{" "}
                  {result.valid_rows.length === 1 ? "lead" : "leads"}
                </Button>
              </div>
            ) : (
              <div className="mt-4">
                <Button
                  onClick={() => {
                    navigate("/leads");
                  }}
                >
                  View leads
                </Button>
              </div>
            )}
          </Card>
          {result.invalid_rows.length > 0 ? (
            <Card>
              <h2 className="text-h4 font-semibold text-ink">
                {result.invalid_rows.length}{" "}
                {result.invalid_rows.length === 1 ? "row needs" : "rows need"} a fix
              </h2>
              <ul className="mt-4 divide-y divide-gray-200">
                {result.invalid_rows.map((row) => (
                  <li key={row.row_number} className="py-3">
                    <p className="font-medium text-ink">Row {row.row_number}</p>
                    <p className="text-small text-danger">{row.message}</p>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
