import { useNavigate } from "react-router-dom";
import { Compass, FileText } from "lucide-react";

import { MockupGallery } from "../features/mockups/MockupGallery";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";

export function MockupsPage() {
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Mockups"
        description="Visual homepage concepts prepared from prospect brand intelligence and website gaps."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              className="h-9 px-3 text-small"
              onClick={() => navigate("/design-md")}
            >
              <FileText className="size-4 mr-1 text-gray-500" />
              <span>Design MD Guides</span>
            </Button>
            <Button
              variant="secondary"
              className="h-9 px-3 text-small"
              onClick={() => navigate("/discover")}
            >
              <Compass className="size-4 mr-1 text-gray-500" />
              <span>Find Leads</span>
            </Button>
          </div>
        }
      />
      <MockupGallery />
    </>
  );
}
