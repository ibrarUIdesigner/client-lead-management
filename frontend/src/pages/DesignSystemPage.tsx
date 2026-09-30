import { useState } from "react";

import { DataTable, type DataColumn } from "../components/data/DataTable";
import { EmptyState } from "../components/feedback/EmptyState";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Checkbox } from "../components/ui/Checkbox";
import { Drawer } from "../components/ui/Drawer";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { RadioGroup } from "../components/ui/RadioGroup";
import { Select } from "../components/ui/Select";
import { Skeleton } from "../components/ui/Skeleton";
import { Switch } from "../components/ui/Switch";
import { Tabs } from "../components/ui/Tabs";
import { Textarea } from "../components/ui/Textarea";

type SampleRow = {
  id: string;
  business: string;
  status: string;
};

const sampleRows: SampleRow[] = [
  { id: "1", business: "Northwind Cafe", status: "NEW" },
  { id: "2", business: "Harbor Dental", status: "QUALIFIED" },
  { id: "3", business: "Lumen Studio", status: "CONTACTED" },
  { id: "4", business: "Field & Rye", status: "REPLIED" },
];

const columns: DataColumn<SampleRow>[] = [
  { id: "business", header: "Business", cell: (row) => row.business },
  { id: "status", header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
];

const pageSize = 2;

export function DesignSystemPage() {
  const { notify } = useToast();
  const [industry, setIndustry] = useState("cafe");
  const [priority, setPriority] = useState("normal");
  const [includeNotes, setIncludeNotes] = useState(true);
  const [reminders, setReminders] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [page, setPage] = useState(1);

  const pageCount = Math.ceil(sampleRows.length / pageSize);
  const visibleRows = sampleRows.slice((page - 1) * pageSize, page * pageSize);

  return (
    <>
      <PageHeader
        title="Design system"
        description="Shared controls for the workspace. Product screens use these same pieces."
      />

      <div className="flex flex-col gap-8">
        <Card>
          <h2 className="text-h3 font-semibold">Buttons</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button>Save lead</Button>
            <Button variant="secondary">Cancel</Button>
            <Button variant="ghost">Dismiss</Button>
            <Button isLoading>Saving</Button>
            <Button
              onClick={() => {
                notify("Changes saved.", "success");
              }}
            >
              Show notice
            </Button>
          </div>
        </Card>

        <Card>
          <h2 className="text-h3 font-semibold">Fields</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Input label="Business name" placeholder="Northwind Cafe" />
            <Select
              label="Industry"
              value={industry}
              options={[
                { value: "cafe", label: "Cafe" },
                { value: "clinic", label: "Clinic" },
                { value: "studio", label: "Studio" },
              ]}
              onChange={(event) => {
                setIndustry(event.target.value);
              }}
            />
            <div className="md:col-span-2">
              <Textarea label="Notes" placeholder="What needs a better website?" />
            </div>
            <Input label="Website" error="Enter a public website address." defaultValue="notaurl" />
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Checkbox
              label="Keep notes on the lead"
              checked={includeNotes}
              onChange={(event) => {
                setIncludeNotes(event.target.checked);
              }}
            />
            <RadioGroup
              label="Priority"
              name="priority"
              value={priority}
              options={[
                { value: "normal", label: "Normal" },
                { value: "high", label: "High" },
              ]}
              onChange={setPriority}
            />
            <Switch
              label="Follow-up reminders"
              checked={reminders}
              onCheckedChange={setReminders}
            />
          </div>
        </Card>

        <Card>
          <h2 className="text-h3 font-semibold">Status</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge>Neutral</Badge>
            <StatusBadge status="NEW" />
            <StatusBadge status="QUALIFIED" />
            <StatusBadge status="CONTACTED" />
            <StatusBadge status="REPLIED" />
            <StatusBadge status="MEETING" />
            <StatusBadge status="WON" />
            <StatusBadge status="LOST" />
          </div>
        </Card>

        <Card>
          <h2 className="text-h3 font-semibold">Tabs</h2>
          <div className="mt-4">
            <Tabs
              label="Lead sections"
              tabs={[
                {
                  id: "overview",
                  label: "Overview",
                  content: <p>Business details stay in view.</p>,
                },
                {
                  id: "audit",
                  label: "Audit",
                  content: <p>Website findings will show up here.</p>,
                },
                {
                  id: "outreach",
                  label: "Outreach",
                  content: <p>Editable drafts will show up here.</p>,
                },
              ]}
            />
          </div>
        </Card>

        <Card>
          <h2 className="text-h3 font-semibold">Feedback</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setModalOpen(true);
              }}
            >
              Open dialog
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setDrawerOpen(true);
              }}
            >
              Open drawer
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setTableLoading((current) => !current);
              }}
            >
              {tableLoading ? "Show rows" : "Show loading"}
            </Button>
          </div>
          <div className="mt-6 max-w-sm space-y-2" aria-hidden="true">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-10 w-full" />
          </div>
          <div className="mt-6">
            <EmptyState
              title="No mockups yet"
              description="A homepage concept will show up here after an audit."
            />
          </div>
        </Card>

        <section>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-h3 font-semibold">Data table</h2>
          </div>
          <DataTable
            columns={columns}
            rows={visibleRows}
            getRowId={(row) => row.id}
            isLoading={tableLoading}
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
          />
        </section>
      </div>

      <Modal
        open={modalOpen}
        title="Confirm archive"
        description="Archived mockups stay available, but they leave the active list."
        onClose={() => {
          setModalOpen(false);
        }}
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setModalOpen(false);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              setModalOpen(false);
              notify("Mockup archived.", "success");
            }}
          >
            Archive
          </Button>
        </div>
      </Modal>

      <Drawer
        open={drawerOpen}
        title="Filters"
        onClose={() => {
          setDrawerOpen(false);
        }}
      >
        <p className="text-body text-gray-600">
          Status, industry, and city filters will live here.
        </p>
      </Drawer>
    </>
  );
}
