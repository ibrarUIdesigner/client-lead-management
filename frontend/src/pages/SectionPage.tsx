import { EmptyState } from "../components/feedback/EmptyState";
import { PageHeader } from "../components/layout/PageHeader";

type SectionPageProps = {
  title: string;
  description: string;
};

export function SectionPage({ title, description }: SectionPageProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState title={`No ${title.toLowerCase()} yet`} description={description} />
    </>
  );
}
