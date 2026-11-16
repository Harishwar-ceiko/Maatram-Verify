import { AppShell } from "../../components/AppShell";
import { ApplicationsBrowser } from "../../components/ApplicationsBrowser";
import { PageHeader } from "../../components/ui";

export function ApplicationsPage() {
  return (
    <AppShell>
      <PageHeader
        title="My applications"
        description="Every file you have started, with its current status. Open one to see its checks."
      />
      <ApplicationsBrowser />
    </AppShell>
  );
}
