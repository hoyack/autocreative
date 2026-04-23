// Plan 21-08 Task 1 — replaces the plan-21-03 stub.
//
// Typed form for /social/posts/new that mirrors PostCreateRequest (see
// flyer_generator/api/schemas/social.py:14-36) and the Platform / Intent
// literal aliases from flyer_generator/social/models.py:18-19. Submits
// POST /api/v1/social/posts and navigates to /social/posts/:job_id on
// success.
//
// .strict() mirrors Pydantic's model_config = ConfigDict(extra="forbid")
// so any unexpected field fails client-side before a wasted round-trip.
//
// Security (21-08-PLAN.md <threat_model>):
// - T-2 (XSS): every form field renders via JSX text children, which React
//   escapes. No raw-HTML injection points exist. Server error bodies are
//   surfaced through toast.error() which also renders as text.
// - T-6 (length limits): zod .max(400) on topic + image_hint, .max(200) on
//   cta, .max(64) on brand_kit_slug + style_preset all mirror Pydantic.
// - T-17 (platform/intent enum smuggling): z.enum(PLATFORMS) /
//   z.enum(INTENTS) rejects unknown values at form-validate time; Pydantic
//   Literal[] re-rejects on the server as defense in depth.
//
// v1 scope: the status page shows the rendered image via <JobStatusCard/>.
// PostRecord.audit_report and validation_report are NOT surfaced by the
// v1 API — documented in status.tsx. A future polish plan would add a
// dedicated JSON read route and render them here.
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  type ApiErrorBody,
  type PostCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";

// Mirrors flyer_generator/api/schemas/social.py::PostCreateRequest and
// flyer_generator/social/models.py Platform + Intent literal aliases.
const SLUG = /^[a-z0-9][a-z0-9-]*$/;
const PLATFORMS = [
  "linkedin",
  "twitter",
  "instagram",
  "facebook",
] as const;
const INTENTS = ["announcement", "value-prop", "testimonial"] as const;

// .strict() mirrors Pydantic's extra="forbid" (21-PATTERNS.md "Pattern:
// Pydantic extra=forbid -> zod .strict()"). No z.string().default(...) used
// anywhere — see plan 21-06 key-decision on zod v4's input/output type
// bifurcation breaking the RHF Resolver<T> generic-equality check. All
// defaults are seeded via RHF's useForm({ defaultValues }) instead.
const PostFormSchema = z
  .object({
    brand_kit_slug: z
      .string()
      .min(1)
      .max(64)
      .regex(SLUG, "lowercase letters, digits, dashes"),
    platform: z.enum(PLATFORMS),
    intent: z.enum(INTENTS),
    topic: z.string().min(1).max(400),
    cta: z.string().max(200).optional(),
    image_hint: z.string().max(400).optional(),
    style_preset: z.string().max(64).optional(),
  })
  .strict();

type PostFormValues = z.infer<typeof PostFormSchema>;

export function NewSocialPostPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Pre-fill brand-kit slug when navigated from a brand-kit detail page's
  // "Use in post" cross-link (mirrors the 21-05 / 21-06 pattern; per T-3
  // disposition brand-kit slugs are non-secret in the single-user trust
  // model).
  const brandKitFromQuery = searchParams.get("brand_kit") ?? "";

  const form = useForm<PostFormValues>({
    resolver: zodResolver(PostFormSchema),
    defaultValues: {
      brand_kit_slug: brandKitFromQuery,
      platform: "linkedin",
      intent: "announcement",
      topic: "",
      cta: "",
      image_hint: "",
      style_preset: "",
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: PostFormValues) => {
      // Strip empty optional strings so the Pydantic extra="forbid" server
      // doesn't see a meaningless ""; absent maps to Field(default=None)
      // literally. Required fields are always forwarded as-is.
      const body: PostCreateRequestBody = {
        brand_kit_slug: values.brand_kit_slug,
        platform: values.platform,
        intent: values.intent,
        topic: values.topic,
        ...(values.cta ? { cta: values.cta } : {}),
        ...(values.image_hint ? { image_hint: values.image_hint } : {}),
        ...(values.style_preset
          ? { style_preset: values.style_preset }
          : {}),
      };
      const { data, error, response } = await client.POST(
        "/api/v1/social/posts",
        { body },
      );
      if (error) {
        const e = error as ApiErrorBody;
        throw new Error(
          typeof e.detail === "string"
            ? e.detail
            : `HTTP ${response.status}`,
        );
      }
      return data!;
    },
    onSuccess: ({ job_id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      toast.success(`Post enqueued (${job_id.slice(0, 8)}...)`);
      navigate(`/social/posts/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">New social post</h1>
      <p className="text-muted-foreground text-sm">
        Pick a platform + intent, describe the topic, and submit. The
        pipeline enqueues a job and the next page polls it until the
        rendered image appears.
      </p>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((v) => enqueue.mutate(v))}
          className="space-y-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="brand_kit_slug"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Brand kit slug</FormLabel>
                <FormControl>
                  <Input placeholder="example-co" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-3">
            <FormField
              control={form.control}
              name="platform"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Platform</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a platform" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {PLATFORMS.map((p) => (
                        <SelectItem key={p} value={p}>
                          {p}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="intent"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Intent</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select an intent" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {INTENTS.map((i) => (
                        <SelectItem key={i} value={i}>
                          {i}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="topic"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Topic</FormLabel>
                <FormControl>
                  <Textarea
                    rows={3}
                    placeholder="Q2 product launch"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="cta"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Call to action (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Learn more"
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="image_hint"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Image hint (optional)</FormLabel>
                <FormControl>
                  <Textarea
                    rows={2}
                    placeholder="lush green landscape, dramatic lighting"
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="style_preset"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Style preset (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="photorealistic"
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" disabled={enqueue.isPending}>
            {enqueue.isPending ? "Submitting..." : "Generate post"}
          </Button>
        </form>
      </Form>
    </div>
  );
}
