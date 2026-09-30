import { MessageList } from "../features/outreach/MessageList";
import { PageHeader } from "../components/layout/PageHeader";

export function OutreachPage() {
  return (
    <>
      <PageHeader
        title="Outreach"
        description="Notes prepared for a prospect. Review a draft before you send it."
      />
      <MessageList />
    </>
  );
}
