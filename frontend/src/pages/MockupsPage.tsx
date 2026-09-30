import { MockupGallery } from "../features/mockups/MockupGallery";
import { PageHeader } from "../components/layout/PageHeader";

export function MockupsPage() {
  return (
    <>
      <PageHeader
        title="Mockups"
        description="Homepage concepts prepared from a prospect's brand and website gaps."
      />
      <MockupGallery />
    </>
  );
}
