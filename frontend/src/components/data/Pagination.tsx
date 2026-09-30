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
        disabled={page <= 1}
        onClick={() => {
          onPageChange(page - 1);
        }}
      >
        Previous
      </Button>
      <p className="text-small text-gray-600">
        Page {page} of {pageCount}
      </p>
      <Button
        variant="secondary"
        disabled={page >= pageCount}
        onClick={() => {
          onPageChange(page + 1);
        }}
      >
        Next
      </Button>
    </nav>
  );
}
