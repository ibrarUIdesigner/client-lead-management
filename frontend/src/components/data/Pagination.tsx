import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "../ui/Button";

type PaginationProps = {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
};

export function Pagination({ page, pageCount, onPageChange }: PaginationProps) {
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3">
      <Button
        variant="secondary"
        size="sm"
        disabled={page <= 1}
        onClick={() => {
          onPageChange(page - 1);
        }}
        className="gap-1 px-2.5"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Previous</span>
      </Button>
      <p className="text-small font-medium text-gray-600">
        Page <span className="font-semibold text-ink">{page}</span> of{" "}
        <span className="font-semibold text-ink">{pageCount}</span>
      </p>
      <Button
        variant="secondary"
        size="sm"
        disabled={page >= pageCount}
        onClick={() => {
          onPageChange(page + 1);
        }}
        className="gap-1 px-2.5"
      >
        <span className="hidden sm:inline">Next</span>
        <ChevronRight className="size-4" aria-hidden="true" />
      </Button>
    </nav>
  );
}
