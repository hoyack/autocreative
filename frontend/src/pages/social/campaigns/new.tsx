// Plan 21-09 Task 1 — replaces the plan-21-03 stub.
//
// Typed form for /social/campaigns/new that mirrors CampaignCreateRequest
// (see flyer_generator/api/schemas/social.py:39-56) and the Platform /
// Intent literal aliases from flyer_generator/social/models.py. Submits
// POST /api/v1/social/campaigns and navigates to
// /social/campaigns/:job_id on success.
//
// Differs from the social post creator (plan 21-08) in ONE place: the
// single `platform` Select is replaced by a `platforms` Checkbox group
// (z.array(z.enum(PLATFORMS)).min(1).max(10)) — this is the array
// result_ref branch of JobStatusCard.tsx (plan 21-04) exercised
// end-to-end.
//
// .strict() mirrors Pydantic's model_config = ConfigDict(extra="forbid")
// so any unexpected field fails client-side before a wasted round-trip.
//
// Security (21-09-PLAN.md <threat_model>):
// - T-2 (XSS): every form field + server-derived string renders via JSX
//   text children, which React escapes. No raw-HTML injection points.
// - T-6 (length limits): zod .max(400) on topic, .max(200) on cta,
//   .max(64) on brand_kit_slug + style_preset, .max(10) on platforms
//   array all mirror Pydantic.
// - T-17 (platform/intent enum smuggling): z.enum(PLATFORMS) /
//   z.enum(INTENTS) + platforms-is-array-of-enum rejects unknown values
//   at form-validate time; Pydantic Literal[] re-rejects server-side.
//
// Pattern notes for future plans:
// - Empty optional strings (cta, style_preset) are stripped in the
//   mutationFn so the server sees absent => Field(default=None). This
//   mirrors the 21-08 decision.
// - RHF's Controller is used for `platforms` (array-valued field) since
//   FormField + zodResolver would otherwise fight the array-of-enum
//   resolver output.
// - Defaults are seeded via useForm({ defaultValues }) rather than
//   z.*.default() — see plan 21-06 key-decision on zod v4's input/output
//   type bifurcation breaking the RHF Resolver<T> generic-equality check.
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  type ApiErrorBody,
  type CampaignCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";

// Mirrors flyer_generator/api/schemas/social.py::CampaignCreateRequest
// and flyer_generator/social/models.py Platform + Intent literal aliases.
const SLUG = /^[a-z0-9][a-z0-9-]*$/;
const PLATFORMS = [
  "linkedin",
  "twitter",
  "instagram",
  "facebook",
] as const;
const INTENTS = ["announcement", "value-prop", "testimonial"] as const;

// .strict() mirrors Pydantic's extra="forbid" (21-PATTERNS.md "Pattern:
// Pydantic extra=forbid -> zod .strict()"). platforms is an
// array-of-enum with min(1) / max(10) bounds mirroring
// Field(min_length=1, max_length=10).
const CampaignFormSchema = z
  .object({
    brand_kit_slug: z
      .string()
      .min(1)
      .max(64)
      .regex(SLUG, "lowercase letters, digits, dashes"),
    platforms: z
      .array(z.enum(PLATFORMS))
      .min(1, "select at least one platform")
      .max(10),
    intent: z.enum(INTENTS),
    topic: z.string().min(1).max(400),
    cta: z.string().max(200).optional(),
    style_preset: z.string().max(64).optional(),
  })
  .strict();

type CampaignFormValues = z.infer<typeof CampaignFormSchema>;

export function NewCampaignPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Pre-fill brand-kit slug when navigated from brand-kit detail's
  // "Use in campaign" cross-link (mirrors 21-05 / 21-06 / 21-08 pattern;
  // per T-3 disposition brand-kit slugs are non-secret in the single-
  // user trust model).
  const brandKitFromQuery = searchParams.get("brand_kit") ?? "";

  const form = useForm<CampaignFormValues>({
    resolver: zodResolver(CampaignFormSchema),
    defaultValues: {
      brand_kit_slug: brandKitFromQuery,
      platforms: [],
      intent: "announcement",
      topic: "",
      cta: "",
      style_preset: "",
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: CampaignFormValues) => {
      // Strip empty optional strings so the Pydantic extra="forbid"
      // server doesn't see a meaningless ""; absent maps to
      // Field(default=None) literally. Required fields are always
      // forwarded as-is.
      const body: CampaignCreateRequestBody = {
        brand_kit_slug: values.brand_kit_slug,
        platforms: values.platforms,
        intent: values.intent,
        topic: values.topic,
        ...(values.cta ? { cta: values.cta } : {}),
        ...(values.style_preset
          ? { style_preset: values.style_preset }
          : {}),
      };
      const { data, error, response } = await client.POST(
        "/api/v1/social/campaigns",
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
      toast.success(`Campaign enqueued (${job_id.slice(0, 8)}...)`);
      navigate(`/social/campaigns/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">New campaign</h1>
      <p className="text-muted-foreground text-sm">
        Pick one or more platforms, describe the topic, and submit. The
        pipeline enqueues ONE job that produces one rendered image per
        selected platform; the status page shows the per-platform grid.
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

          {/*
           * Platforms multi-select. FormField is used (which itself wraps
           * RHF's Controller and provides the FormFieldContext that
           * FormLabel / FormMessage need). The field is array-valued and
           * we drive each Checkbox's `checked` + `onCheckedChange`
           * imperatively from the current array value. Each Checkbox is
           * wrapped in a <label> whose click delegates to the control —
           * this is the selector the plan's valid-submit test uses
           * (userEvent.click(screen.getByText("linkedin"))).
           *
           * [Rule 1 - Bug] The plan's sample code used a raw Controller
           * with FormItem + FormLabel; FormLabel throws "useFormField
           * should be used within <FormField>" because Controller alone
           * does NOT populate FormFieldContext. Fix: use FormField which
           * is literally Controller + FormFieldContext.Provider.
           */}
          <FormField
            control={form.control}
            name="platforms"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>Platforms</FormLabel>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {PLATFORMS.map((p) => {
                    const checked = field.value?.includes(p) ?? false;
                    return (
                      <label
                        key={p}
                        className="flex items-center gap-2 rounded-lg border border-input px-3 py-2 text-sm"
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(v) => {
                            const next = new Set(field.value ?? []);
                            if (v) next.add(p);
                            else next.delete(p);
                            // Preserve the canonical PLATFORMS order so
                            // the submitted array is stable and matches
                            // the enum declaration order — a tidier
                            // body contract than insertion-order.
                            const canonical = PLATFORMS.filter((x) =>
                              next.has(x),
                            );
                            field.onChange(canonical);
                          }}
                        />
                        <span>{p}</span>
                      </label>
                    );
                  })}
                </div>
                {fieldState.error && (
                  <p className="text-sm font-medium text-destructive">
                    {fieldState.error.message}
                  </p>
                )}
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="intent"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Intent</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
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
            {enqueue.isPending ? "Submitting..." : "Generate campaign"}
          </Button>
        </form>
      </Form>
    </div>
  );
}
