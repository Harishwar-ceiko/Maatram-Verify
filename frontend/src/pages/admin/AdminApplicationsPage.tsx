import { AppShell } from "../../components/AppShell";
import { ApplicationsBrowser } from "../../components/ApplicationsBrowser";
import { PageHeader } from "../../components/ui";

export function AdminApplicationsPage() {
  return (
    <AppShell>
      <PageHeader
        title="All applications"
        description="Every applicant and every file. Filter by status or search by reference, name or register number."
      />
      <ApplicationsBrowser admin />
    </AppShell>
  );
}
