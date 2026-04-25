// Plan 22-06 Task 2 — extends Plan 21-06's flyer creator form with:
//   * Template <Select>: 6 options mirroring flyer_generator/flyer/schemas/
//     (editorial_classic, bold_modern, minimal_photo, retro_poster, zine,
//     tight_typographic). Validated as a free-form string at the schema layer
//     (matches FlyerCreateRequest.template: str on the backend); the worker
//     validates the slug at load_template() time.
//   * Subtype <Select>: 2 options ("event" + "info"). Default "event"
//     preserves the Phase-21 contract for any caller still wired against the
//     pre-Phase-22 form.
//   * Conditional event-only fields (date, time, venue_name, venue_address,
//     fees) — visible only when subtype === "event".
//   * Conditional info-only fields (description, call_to_action) — visible
//     only when subtype === "info".
//
// .strict() mirrors Pydantic's model_config = ConfigDict(extra="forbid")
// on both the outer FlyerCreateRequest and the nested FlyerInput. Any
// unexpected field fails client-side before a wasted round-trip.
//
// Subtype-conditional validation uses .superRefine (not z.discriminatedUnion):
// per 22-CONTEXT line 80-85 either is acceptable; superRefine avoids the RHF
// zodResolver discriminated-union resolver quirks documented in the
// Plan 21-06 deviation note.
//
// Preset duplication: 21-RESEARCH.md line 334 + 21-PATTERNS.md line 298
// note that FlyerInput.style_preset and FlyerCreateRequest.preset are
// duplicated by design. This form accepts ONE preset selection and copies
// it into both fields at submit time.
//
// Security (21-06 + 22-06 threat model T-22-13/T-22-14):
// - T-2 (XSS): every form field renders via JSX text children, which React
//   escapes. No raw-HTML injection points exist. Server validation error
//   bodies are surfaced through toast.error() which also renders as text.
// - T-22-13 (template tampering): if a user submits a template not in the
//   TEMPLATES tuple by editing DOM/network, the worker rejects it via
//   _validate_template_slug + load_template (FileNotFoundError → job fails).
//   Defense-in-depth: zod z.enum(TEMPLATES) on the FE is a UX nicety only.
// - T-6 (length limits): zod .max(120) mirrors Pydantic max_length=120 on
//   every FlyerInput field; .max(64) on preset/brand_kit_slug; .regex(HEX)
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

// 22-CONTEXT line 41 — 6 templates ship at launch. Hardcoded per
// 22-CONTEXT line 23-24 (template-discovery API deferred; mirrors brochure
// template-hardcoded precedent).
const TEMPLATES = [
  "editorial_classic",
  "bold_modern",
  "minimal_photo",
  "retro_poster",
  "zine",
  "tight_typographic",
] as const;

// 22-CONTEXT line 49-52 — single FlyerInput model with subtype field.
const SUBTYPES = ["event", "info"] as const;

// Mirrors flyer_generator/api/schemas/flyers.py::FlyerCreateRequest +
// flyer_generator/models.py::FlyerInput. .strict() on BOTH objects per
// 21-PATTERNS.md line 629.
//
// All FlyerInput fields except `title`, `subtype`, `org`, `style_concept`,
// `style_preset`, `color_accent` are zod-optional at the field level;
// .superRefine below enforces subtype-specific requirements:
//   * subtype === "event" -> date, time, location_name, location_address required
//   * subtype === "info"  -> description required
// This matches the Phase-22 backend behavior where event-only fields are
// optional on FlyerInput and the vision/composer branch on subtype.
//
// We DO NOT use z.string().default(...) anywhere (zod v4's .default()
// breaks the RHF Resolver<T> generic-equality check — Plan 21-06 deviation
// #1). Seed defaults via useForm.defaultValues below instead.
const FlyerFormSchema = z
  .object({
    event: z
      .object({
        title: z.string().min(1).max(120),
        subtype: z.enum(SUBTYPES),
        // Event-only — optional at field level, gated by superRefine below.
        date: z.string().max(120).optional(),
        time: z.string().max(120).optional(),
        location_name: z.string().max(120).optional(),
        location_address: z.string().max(120).optional(),
        fees: z.string().max(120).optional(),
        // Info-only — optional at field level, gated by superRefine below.
        description: z.string().max(600).optional(),
        call_to_action: z.string().max(120).optional(),
        // Shared
        org: z.string().max(120),
        url: z.string().url().nullable().optional(),
        style_concept: z.string().min(1).max(120),
        style_preset: z.string().max(120),
        color_accent: z.string().regex(HEX),
      })
      .strict()
      .superRefine((val, ctx) => {
        if (val.subtype === "event") {
          for (const req of [
            "date",
            "time",
            "location_name",
            "location_address",
          ] as const) {
            if (!val[req] || val[req]!.trim().length === 0) {
              ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: [req],
                message: "Required for event flyers",
              });
            }
          }
        } else {
          // subtype === "info"
          if (!val.description || val.description.trim().length === 0) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              path: ["description"],
              message: "Required for info flyers",
            });
          }
        }
      }),
    template: z.enum(TEMPLATES),
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
  // Pre-fill subtype from `?subtype=info` (mirrors brand_kit query-string
  // pattern) — supports cross-links like "Send a notice" buttons.
  const subtypeFromQuery = searchParams.get("subtype");
  const initialSubtype: (typeof SUBTYPES)[number] =
    subtypeFromQuery === "info" ? "info" : "event";

  const form = useForm<FlyerFormValues>({
    resolver: zodResolver(FlyerFormSchema),
    defaultValues: {
      preset: "photorealistic",
      template: "editorial_classic",
      brand_kit_slug: brandKitFromQuery,
      event: {
        title: "",
        subtype: initialSubtype,
        date: "",
        time: "",
        location_name: "",
        location_address: "",
        fees: "",
        description: "",
        call_to_action: "",
        org: "",
        style_concept: "",
        style_preset: "photorealistic",
        color_accent: "#F59E0B",
      },
    },
  });

  // Watch subtype for conditional rendering. Plan 22-06 step 4.
  const subtype = form.watch("event.subtype");

  const enqueue = useMutation({
    mutationFn: async (values: FlyerFormValues) => {
      // Preset duplication (21-RESEARCH.md line 334): the chosen `preset`
      // must land in BOTH the top-level `preset` and the nested
      // `event.style_preset`. Cast via FlyerCreateRequestBody so a Phase 20
      // schema change surfaces as a compile error at this call site.
      //
      // Empty-string optional fields are coerced to null before POST: zod
      // .optional() accepts "" but the backend's Pydantic `str | None`
      // doesn't discriminate empty strings — they would pass through and
      // get persisted. Send null so the worker treats absent fields as
      // truly absent (Phase-22 vision/composer logic checks `is None`).
      const cleanedEvent = {
        ...values.event,
        style_preset: values.preset,
        date: values.event.date || null,
        time: values.event.time || null,
        location_name: values.event.location_name || null,
        location_address: values.event.location_address || null,
        fees: values.event.fees || null,
        description: values.event.description || null,
        call_to_action: values.event.call_to_action || null,
        url: values.event.url || null,
      };
      const body: FlyerCreateRequestBody = {
        ...values,
        event: cleanedEvent,
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
        dek="Pick a template and subtype, fill the fields, and submit. The pipeline enqueues a job and the next page polls it until the rendered PNG lands."
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
          <FormField
            control={form.control}
            name="event.subtype"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Subtype</FormLabel>
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <FormControl>
                    <SelectTrigger data-testid="subtype-select">
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {SUBTYPES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          {subtype === "event" && (
            <>
              <div className="grid grid-cols-2 gap-8">
                <FormField
                  control={form.control}
                  name="event.date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Date</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="2026-05-01"
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
                  name="event.time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Time</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="7:00 PM"
                          {...field}
                          value={field.value ?? ""}
                        />
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
                      <Input
                        placeholder="The Hall"
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
                name="event.location_address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Venue address</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="1 Main St"
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
                name="event.fees"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Fees</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Free"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          )}
          {subtype === "info" && (
            <>
              <FormField
                control={form.control}
                name="event.description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the message, notice, or announcement…"
                        rows={4}
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
                name="event.call_to_action"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Call to action (optional)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Visit www.example.com"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          )}
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
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="template"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Template</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                  >
                    <FormControl>
                      <SelectTrigger data-testid="template-select">
                        <SelectValue placeholder="Select a template" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {TEMPLATES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
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
          </div>
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
