
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "../../components/AppShell";
import { PageHeader } from "../../components/ui";
import { api } from "../../lib/api";

export function StudentsPage() {
  const students = useQuery({
    queryKey: ["admin", "students"],
    queryFn: api.students,
  });

  return (
    <AppShell>
      <PageHeader
        title="Student profiles"
        description="View applicant details, volunteer activities and achievements."
      />

      <div className="card mt-5 overflow-hidden">
        {students.isLoading ? (
          <p className="p-5 text-sm text-muted">Loading student profiles...</p>
        ) : students.isError ? (
          <p className="p-5 text-sm text-fail">
            Could not load student profiles. Please refresh and try again.
          </p>
        ) : !students.data?.length ? (
          <p className="p-5 text-sm text-muted">
            No student accounts registered yet.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Email</th>
                  <th>Volunteer Activities</th>
                  <th>Achievements</th>
                  <th>Applications</th>
                </tr>
              </thead>

              <tbody>
                {students.data.map((student) => (
                  <tr key={student.id}>
                    <td className="font-medium">
                      {student.full_name}
                    </td>

                    <td className="text-muted">
                      {student.email}
                    </td>

                    <td className="max-w-[280px] whitespace-pre-wrap">
                      {student.volunteer_activities?.trim() || (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    <td className="max-w-[280px] whitespace-pre-wrap">
                      {student.achievements?.trim() || (
                        <span className="text-muted">—</span>
                      )}
                    </td>

                    <td className="num">
                      {student.applications}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
