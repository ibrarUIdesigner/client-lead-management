import { MessageList } from "../features/outreach/MessageList";
import { PageHeader } from "../components/layout/PageHeader";

export function OutreachPage() {
  return (
    <>
      <PageHeader
        title="Outreach"
        description="Drafts and sent notes. Open a lead to write one, send it from your email app, then mark it here."
      />
      <MessageList />
    </>
  );
}
