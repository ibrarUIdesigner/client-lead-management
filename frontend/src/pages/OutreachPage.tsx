import { MessageList } from "../features/outreach/MessageList";
import { PageHeader } from "../components/layout/PageHeader";

export function OutreachPage() {
  return (
    <>
      <PageHeader
        title="Outreach"
        description="Each note is written from that lead's audit. Open a lead, send the draft from your email, then mark it here."
      />
      <MessageList />
    </>
  );
}
