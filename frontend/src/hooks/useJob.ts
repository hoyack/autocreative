// Per 21-RESEARCH.md Pattern 3 (lines 728-759) + Pitfall #1 (refetchInterval
// callback receives Query, NOT data — v5 migration) + Pitfall #2 (gcTime, not
// cacheTime — v5 rename; cacheTime is silently ignored).
//
// Every status page in plans 21-05..09 mounts this hook. Polling terminates
// on the JobStatus terminal set {succeeded, failed, cancelled} which is
// mirrored from flyer_generator/api/models/job.py::JobStatus.
import { useQuery } from "@tanstack/react-query";
import { client, isTerminalStatus, type JobDetail } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";

export function useJob(jobId: string) {
  return useQuery<JobDetail>({
    queryKey: queryKeys.job(jobId),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      if (error || !data) throw new Error("failed to fetch job");
      return data;
    },
    // v5: callback receives Query object, NOT data. Read via query.state.data.
    // CRITICAL — copying a v4 example here will break polling termination
    // because `data` would be undefined and isTerminalStatus would never match.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (isTerminalStatus(status)) return false;
      return 1000;
    },
    refetchIntervalInBackground: false,
    // v5: gcTime (NOT cacheTime — silently ignored in v5).
    gcTime: 5 * 60 * 1000,
    staleTime: 0,
  });
}
