// Source: 21-RESEARCH.md Pattern 5 (verbatim, lines 884-922) + wildcard 404
import { createBrowserRouter, Navigate } from "react-router";
import { DashboardLayout } from "@/components/DashboardLayout";
import { ErrorPage } from "@/pages/Error";
import { NotFoundPage } from "@/pages/NotFound";

import { BrandKitsListPage } from "@/pages/brand-kits/list";
import { ScrapeBrandKitPage } from "@/pages/brand-kits/new";
import { BrandKitDetailPage } from "@/pages/brand-kits/detail";

import { NewFlyerPage } from "@/pages/flyers/new";
import { FlyerStatusPage } from "@/pages/flyers/status";

import { NewBrochurePage } from "@/pages/brochures/new";
import { BrochureStatusPage } from "@/pages/brochures/status";

import { NewPostcardPage } from "@/pages/postcards/new";
import { PostcardStatusPage } from "@/pages/postcards/status";

import { NewPosterPage } from "@/pages/posters/new";
import { PosterStatusPage } from "@/pages/posters/status";

import { NewSocialPostPage } from "@/pages/social/posts/new";
import { SocialPostStatusPage } from "@/pages/social/posts/status";

import { NewCampaignPage } from "@/pages/social/campaigns/new";
import { CampaignStatusPage } from "@/pages/social/campaigns/status";

import { JobsListPage } from "@/pages/jobs/list";
import { RenderGalleryPage } from "@/pages/renders/gallery";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <DashboardLayout />,
    errorElement: <ErrorPage />,
    children: [
      // Per 21-RESEARCH.md Open Q#7: land on brand-kits list.
      { index: true, element: <Navigate to="/brand-kits" replace /> },

      { path: "brand-kits", element: <BrandKitsListPage /> },
      { path: "brand-kits/new", element: <ScrapeBrandKitPage /> },
      { path: "brand-kits/:slug", element: <BrandKitDetailPage /> },

      { path: "flyers/new", element: <NewFlyerPage /> },
      { path: "flyers/:id", element: <FlyerStatusPage /> },

      { path: "brochures/new", element: <NewBrochurePage /> },
      { path: "brochures/:id", element: <BrochureStatusPage /> },

      { path: "postcards/new", element: <NewPostcardPage /> },
      { path: "postcards/:id", element: <PostcardStatusPage /> },

      { path: "posters/new", element: <NewPosterPage /> },
      { path: "posters/:id", element: <PosterStatusPage /> },

      { path: "social/posts/new", element: <NewSocialPostPage /> },
      { path: "social/posts/:id", element: <SocialPostStatusPage /> },
      { path: "social/campaigns/new", element: <NewCampaignPage /> },
      { path: "social/campaigns/:id", element: <CampaignStatusPage /> },

      { path: "jobs", element: <JobsListPage /> },
      { path: "renders", element: <RenderGalleryPage /> },

      // Wildcard 404 — every unmatched path under "/" renders NotFoundPage.
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
