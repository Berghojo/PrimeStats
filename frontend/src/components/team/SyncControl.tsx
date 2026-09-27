import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useStartSync, useSyncStatus } from "../../api/hooks";
import type { SyncJob } from "../../api/types";
import { ErrorBox, Spinner } from "../ui";

export function SyncControl({ teamId, initial }: { teamId: number; initial: SyncJob | null }) {
  const qc = useQueryClient();
  const start = useStartSync(teamId);
  const { data } = useSyncStatus(teamId, true);
  const job = data === undefined ? initial : data;
  const previous = useRef(job?.status);

  useEffect(() => {
    if (previous.current === "running" && job?.status === "done") {
      qc.invalidateQueries({ queryKey: ["team", teamId, "report"] });
      qc.invalidateQueries({ queryKey: ["teams"] });
    }
    previous.current = job?.status;
  }, [job?.status, qc, teamId]);

  if (job?.status === "running") {
    return (
      <div className="sync-box" aria-live="polite">
        <Spinner />
        <div>
          <div>{job.message}</div>
          <div className="progress"><span style={{ width: `${job.percent}%` }} /></div>
        </div>
      </div>
    );
  }
  return (
    <div className="sync-box">
      <button className="btn primary" type="button" disabled={start.isPending} onClick={() => start.mutate()}>
        Custom Games synchronisieren
      </button>
      {start.error && <ErrorBox error={start.error} />}
      {job?.status === "error" && <span className="neg">{job.message} {job.error}</span>}
      {job?.status === "done" && <span className="pos">{job.message}</span>}
    </div>
  );
}
