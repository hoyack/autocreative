// Plan 21-06 Task 1 — replaces the plan-21-03 stub.
//
// Typed form for /flyers/new that mirrors FlyerCreateRequest +
// EventInput (see flyer_generator/api/schemas/flyers.py:14-37 and
// flyer_generator/models.py::EventInput). Submits POST /api/v1/flyers and
// navigates to /flyers/:job_id.
//
// .strict() mirrors Pydantic's model_config = ConfigDict(extra="forbid")
// on both the outer FlyerCreateRequest and the nested EventInput. Any
// unexpected field fails client-side before a wasted round-trip.
//
// Preset duplication: 21-RESEARCH.md line 334 + 21-PATTERNS.md line 298
// note that EventInput.style_preset and FlyerCreateRequest.preset are
// duplicated by design. This form accepts ONE preset selection and copies
// it into both fields at submit time.
//
// Security (21-06-PLAN.md <threat_model>):
// - T-2 (XSS): every form field renders via JSX text children, which React
//   escapes. No raw-HTML injection points exist. Server validation error
//   bodies are surfaced through toast.error() which also renders as text.
// - T-6 (length limits): zod .max(120) mirrors Pydantic max_length=120 on
//   every EventInput field; .max(64) on preset/brand_kit_slug; .regex(HEX)
//   on accent + color_accent; .min(1)/.max(10) on max_bg_attempts.
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
  type FlyerCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { PageHeader } from "@/components/PageHeader";

const HEX = /^#[0-9A-Fa-f]{6}$/;
const SLUG = /^[a-z0-9][a-z0-9-]*$/;
const PRESETS = [
  "photorealistic",
  "anime",
  "western_cartoon",
  "scifi",
  "watercolor",
  "retro_poster",
] as const;

// Mirrors flyer_generator/api/schemas/flyers.py::FlyerCreateRequest +
// flyer_generator/models.py::EventInput. .strict() on BOTH objects per
// 21-PATTERNS.md line 629.
// NOTE: we DO NOT use z.string().default(...) on the EventInput fields even
// though Pydantic's EventInput assigns a default to color_accent. Reason:
// zod v4's .default() produces an OPTIONAL input type and a REQUIRED output
// type, and `zodResolver` infers from the INPUT type. Mixing `.default()`
// with `.strict()` inside a nested object breaks the RHF Resolver<T>
// generic-equality check (TS2322 / TS2719 "Two different types with this
// name exist"). Seed defaults via RHF's `defaultValues` below instead — the
// runtime behavior (every field submitted with a concrete value) is the
// same as Pydantic expects.
const FlyerFormSchema = z
  .object({
    event: z
      .object({
        title: z.string().min(1).max(120),
        date: z.string().min(1).max(120),
        time: z.string().min(1).max(120),
        location_name: z.string().min(1).max(120),
        location_address: z.string().min(1).max(120),
        fees: z.string().max(120),
        org: z.string().max(120),
        url: z.string().url().nullable().optional(),
        style_concept: z.string().max(120),
        style_preset: z.string().max(120),
        color_accent: z.string().regex(HEX),
      })
      .strict(),
    preset: z.string().min(1).max(64),
    brand_kit_slug: z
      .string()
      .regex(SLUG, "lowercase letters, digits, dashes")
      .max(64)
      .optional(),
    accent: z.string().regex(HEX).optional(),
    max_bg_attempts: z.number().int().min(1).max(10).optional(),
  })
  .strict();

type FlyerFormValues = z.infer<typeof FlyerFormSchema>;

export function NewFlyerPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Pre-fill brand-kit slug when navigated from a brand-kit detail page's
  // "Use in flyer" link (21-05). Non-secret per T-3 (accept disposition).
  const brandKitFromQuery = searchParams.get("brand_kit") ?? undefined;

  const form = useForm<FlyerFormValues>({
    resolver: zodResolver(FlyerFormSchema),
    defaultValues: {
      preset: "photorealistic",
      brand_kit_slug: brandKitFromQuery,
      event: {
        title: "",
        date: "",
        time: "",
        location_name: "",
        location_address: "",
        fees: "",
        org: "",
        style_concept: "",
        style_preset: "photorealistic",
        color_accent: "#F59E0B",
      },
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: FlyerFormValues) => {
      // Preset duplication (21-RESEARCH.md line 334): the chosen `preset`
      // must land in BOTH the top-level `preset` and the nested
      // `event.style_preset`. Cast via FlyerCreateRequestBody so a Phase 20
      // schema change surfaces as a compile error at this call site.
      const body: FlyerCreateRequestBody = {
        ...values,
        event: { ...values.event, style_preset: values.preset },
      } as FlyerCreateRequestBody;
      const { data, error, response } = await client.POST(
        "/api/v1/flyers",
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
      toast.success(`Flyer enqueued (${job_id.slice(0, 8)}...)`);
      navigate(`/flyers/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="mx-auto max-w-3xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="02"
        kicker="The Canvas"
        title="New flyer"
        dek="Fill the event fields, pick a style preset, and (optionally) a brand kit. The pipeline enqueues a job and the next page polls it until the rendered PNG lands."
      />
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((v) => enqueue.mutate(v))}
          className="space-y-8"
          noValidate
        >
          <FormField
            control={form.control}
            name="event.title"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Title</FormLabel>
                <FormControl>
                  <Input placeholder="Friday Night Show" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="event.date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date</FormLabel>
                  <FormControl>
                    <Input placeholder="2026-05-01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="event.time"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Time</FormLabel>
                  <FormControl>
                    <Input placeholder="7:00 PM" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="event.location_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Venue name</FormLabel>
                <FormControl>
                  <Input placeholder="The Hall" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="event.location_address"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Venue address</FormLabel>
                <FormControl>
                  <Input placeholder="1 Main St" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="event.fees"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Fees</FormLabel>
                  <FormControl>
                    <Input placeholder="Free" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="event.org"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Organization</FormLabel>
                  <FormControl>
                    <Input placeholder="Acme Co" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="event.style_concept"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Style concept</FormLabel>
                <FormControl>
                  <Input placeholder="moody industrial" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="preset"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Preset</FormLabel>
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a preset" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {PRESETS.map((p) => (
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
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="brand_kit_slug"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Brand kit slug (optional)</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="example-co"
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
              name="accent"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Accent override (optional)</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="#F59E0B"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <div className="border-t border-border pt-8">
            <Button
              type="submit"
              size="lg"
              disabled={enqueue.isPending}
              className="w-full sm:w-auto"
            >
              {enqueue.isPending ? "Submitting…" : "Generate flyer →"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
