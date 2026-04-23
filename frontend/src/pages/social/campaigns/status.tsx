// Plan 21-09 Task 1 — replaces the plan-21-03 stub.
//
// Thin wrapper around <JobStatusCard/> (plan 21-04). All polling, status
// states, and render preview logic live inside JobStatusCard so this
// page stays minimal. Mirrors the 21-06 flyer / 21-08 post status page
// pattern verbatim.
//
// IMPORTANT: JobStatusCard already handles BOTH result_ref shapes:
//   - typeof result_ref === "string"  -> single-render jobs (flyer, post)
//   - Array.isArray(result_ref)       -> campaign per-platform grid
//
// Campaigns exercise the array branch: one job => one RenderPreview per
// ResultLink, laid out in a 3-column responsive grid (the grid markup
// lives in JobStatusCard.tsx lines 111-125). This page does NOT need to
// special-case that — it just renders the card.
import { Link, useParams } from "react-router";

import { JobStatusCard } from "@/components/JobStatusCard";

export function CampaignStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="space-y-4">
      <Link to="/social/campaigns/new" className="text-sm underline">
        &larr; New campaign
      </Link>
      <h1 className="text-2xl font-semibold">Campaign job</h1>
      {/*
       * JobStatusCard handles the campaign result_ref array branch — it
       * renders one RenderPreview per ResultLink in a responsive grid.
       */}
      <JobStatusCard jobId={id} title="Campaign" />
    </div>
  );
}
