// Plan 21-07 Task 2 — replaces the plan-21-03 stub.
//
// Form for POST /api/v1/brochures. The BrochureContent shape has nested
// sections[] with body_paragraphs[] + bullets[]; per 21-RESEARCH.md
// "Recommended fallback" (lines 336-348), v1 ships a JSON-paste Textarea
// rather than a nested useFieldArray UX. A polish plan can decompose it later.
//
// Submission flow: zod refine parses the textarea to validate shape, the
// mutationFn then JSON.parses again to produce the actual object that goes
// into body.content. On success we invalidate the jobs query, toast, and
// navigate to /brochures/:job_id (the status page below).
//
// Security (21-07-PLAN.md <threat_model>):
// - T-2 (XSS): every rendered value from the form and the success toast is
//   React text content — escaped. No raw-HTML injection points exist.
// - content textarea is JSON.parse'd client-side then re-validated by
//   Pydantic server-side (extra=forbid on BrochureCreateRequest).
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  type ApiErrorBody,
  type BrochureCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { PageHeader } from "@/components/PageHeader";

const SLUG = /^[a-z0-9][a-z0-9-]*$/;

// Mirrors flyer_generator/api/schemas/brochures.py::BrochureCreateRequest.
// `.strict()` mirrors Pydantic's extra="forbid". Do NOT use z.string().default()
// anywhere — zod v4's .default() breaks the RHF Resolver<T> generic-equality
// check (see plan 21-06 deviation #1). Seed defaults via useForm.defaultValues.
const BrochureFormSchema = z
  .object({
    contentJson: z
      .string()
      .min(2)
      .refine(
        (s) => {
          try {
            JSON.parse(s);
            return true;
          } catch {
            return false;
          }
        },
        { message: "must be valid JSON" },
      ),
    template: z.string().min(1).max(64),
    brand_kit_slug: z
      .string()
      .regex(SLUG, "lowercase letters, digits, dashes")
      .max(64)
      .optional(),
    generate_images: z.boolean(),
    workflow: z.string().min(1).max(64),
    style_preset: z.string().min(1).max(64),
  })
  .strict();

type BrochureFormValues = z.infer<typeof BrochureFormSchema>;

const SAMPLE_CONTENT = JSON.stringify(
  {
    title: "Sample brochure",
    org: "Sample Org",
    sections: [
      {
        heading: "Intro",
        body_paragraphs: ["Hello world."],
        bullets: [],
      },
    ],
  },
  null,
  2,
);

export function NewBrochurePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Pre-fill brand-kit slug when navigated from /brand-kits/:slug's "Use in
  // brochure" cross-link. Non-secret per T-3 (accept disposition).
  const brandKitFromQuery = searchParams.get("brand_kit") ?? undefined;

  const form = useForm<BrochureFormValues>({
    resolver: zodResolver(BrochureFormSchema),
    defaultValues: {
      contentJson: SAMPLE_CONTENT,
      template: "editorial_classic",
      brand_kit_slug: brandKitFromQuery,
      generate_images: true,
      workflow: "turbo_landscape",
      style_preset: "photorealistic",
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: BrochureFormValues) => {
      // Parse the textarea once (already validated by the zod refine above).
      // We destructure `contentJson` off so it doesn't sneak into the POST
      // body (extra="forbid" on the server would 422 otherwise).
      const { contentJson, ...rest } = values;
      const content = JSON.parse(contentJson);
      const body: BrochureCreateRequestBody = {
        ...rest,
        content,
      } as BrochureCreateRequestBody;
      const { data, error, response } = await client.POST(
        "/api/v1/brochures",
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
      toast.success(`Brochure enqueued (${job_id.slice(0, 8)}...)`);
      navigate(`/brochures/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="mx-auto max-w-3xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="03"
        kicker="The Folio"
        title="New brochure"
        dek="Paste a BrochureContent JSON, pick a template, and submit. The pipeline enqueues a job and the next page polls it until the front PNG, back PNG, and print PDF land."
      />
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((v) => enqueue.mutate(v))}
          className="space-y-8"
          noValidate
        >
          <FormField
            control={form.control}
            name="contentJson"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Content (BrochureContent JSON)</FormLabel>
                <FormControl>
                  <Textarea
                    rows={14}
                    className="font-mono text-xs"
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Required keys: <code>title</code>, <code>org</code>,{" "}
                  <code>sections[]</code>. Each section needs{" "}
                  <code>heading</code> + <code>body_paragraphs[]</code>.
                </FormDescription>
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
                  <FormControl>
                    <Input placeholder="editorial_classic" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
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
          </div>
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="workflow"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Workflow</FormLabel>
                  <FormControl>
                    <Input placeholder="turbo_landscape" {...field} />
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
                  <FormLabel>Style preset</FormLabel>
                  <FormControl>
                    <Input placeholder="photorealistic" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="generate_images"
            render={({ field }) => (
              <FormItem className="flex items-center gap-3">
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormLabel className="!mt-0">
                  Generate images via ComfyCloud
                </FormLabel>
              </FormItem>
            )}
          />
          <div className="border-t border-border pt-8">
            <Button
              type="submit"
              size="lg"
              disabled={enqueue.isPending}
              className="w-full sm:w-auto"
            >
              {enqueue.isPending ? "Submitting…" : "Generate brochure →"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
