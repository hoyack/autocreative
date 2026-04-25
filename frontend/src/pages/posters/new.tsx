// Plan 24-05 Task 1 — poster creator page (PO-04).
//
// Mirrors frontend/src/pages/postcards/new.tsx, but a poster has no
// address-block toggle and adds two locked-set Selects:
//   * size      — exactly 3 print sizes (CONTEXT.md D-XX): 18x24, 24x36, 27x40
//   * template  — exactly 3 poster templates (CONTEXT.md D-XX):
//                 editorial_grand, bold_announcement, cinematic_onesheet
//   * style_preset — reuses the flyer's preset list (verbatim).
//
// Editorial PageHeader uses number="09" + kicker="The Big One" — the
// PageHeader component composes the locked "09 / THE BIG ONE" string
// from these two pieces (CONTEXT.md kicker lock).
//
// Security (24-05 threat model T-24-16/T-24-17):
//   - Every form value renders as React JSX text (no dangerouslySetInnerHTML).
//   - Zod .strict() mirrors backend Pydantic extra="forbid".
//   - Size enum on FE is UX nicety; backend Literal["18x24","24x36","27x40"]
//     is authoritative (T-24-17 accept disposition).
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  type ApiErrorBody,
  type PosterCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { PageHeader } from "@/components/PageHeader";

const SLUG = /^[a-z0-9][a-z0-9-]*$/;

// CONTEXT.md D-XX: exactly 3 sizes ship at v1 (locked Pydantic Literal).
const SIZES = ["18x24", "24x36", "27x40"] as const;

// CONTEXT.md D-XX: 3 poster templates ship at launch.
const TEMPLATES = [
  "editorial_grand",
  "bold_announcement",
  "cinematic_onesheet",
] as const;

// Mirrors flyer creator's preset list; posters reuse the same Comfy presets.
const PRESETS = [
  "photorealistic",
  "anime",
  "western_cartoon",
  "scifi",
  "watercolor",
  "retro_poster",
] as const;

// Mirrors flyer_generator/api/schemas/posters.py::PosterCreateRequest.
// `.strict()` mirrors Pydantic's extra="forbid". Do NOT use z.string().default()
// anywhere — zod v4's .default() breaks the RHF Resolver<T> generic-equality
// check (see plan 21-06 deviation #1). Seed defaults via useForm.defaultValues.
const PosterFormSchema = z
  .object({
    headline: z.string().min(1, "headline is required").max(120),
    subheading: z.string().max(200).optional(),
    cta_text: z.string().max(120).optional(),
    image_hint: z.string().max(500).optional(),
    brand_kit_slug: z
      .string()
      .regex(SLUG, "lowercase letters, digits, dashes")
      .max(64)
      .optional()
      .or(z.literal("")),
    style_preset: z.string().min(1).max(64),
    template: z.enum(TEMPLATES),
    size: z.enum(SIZES),
  })
  .strict();

type PosterFormValues = z.infer<typeof PosterFormSchema>;

export function NewPosterPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const form = useForm<PosterFormValues>({
    resolver: zodResolver(PosterFormSchema),
    defaultValues: {
      headline: "",
      subheading: "",
      cta_text: "",
      image_hint: "",
      brand_kit_slug: "",
      style_preset: "photorealistic",
      template: "editorial_grand",
      size: "18x24",
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: PosterFormValues) => {
      const body: PosterCreateRequestBody = {
        headline: values.headline,
        subheading: values.subheading?.trim() ? values.subheading : null,
        cta_text: values.cta_text?.trim() ? values.cta_text : null,
        image_hint: values.image_hint?.trim() ? values.image_hint : null,
        brand_kit_slug: values.brand_kit_slug?.trim()
          ? values.brand_kit_slug
          : null,
        style_preset: values.style_preset,
        template: values.template,
        size: values.size,
      };
      const { data, error, response } = await client.POST(
        "/api/v1/posters",
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
      toast.success(`Poster enqueued (${job_id.slice(0, 8)}…)`);
      navigate(`/posters/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="mx-auto max-w-3xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="09"
        kicker="The Big One"
        title="New poster"
        dek="Pick a print size, a template, and brand context. The pipeline reuses the flyer renderer at the larger canvas — same artwork engine, scaled typography."
      />
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((v) => enqueue.mutate(v))}
          className="space-y-8"
          noValidate
        >
          <FormField
            control={form.control}
            name="headline"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Headline</FormLabel>
                <FormControl>
                  <Input placeholder="Friday Night Show" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="subheading"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Subheading (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="An evening of new music"
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
            name="cta_text"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Call to action (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Tickets at example.com"
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
                    placeholder="A field of poppies at dusk"
                    rows={3}
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
          <div className="grid grid-cols-2 gap-8">
            <FormField
              control={form.control}
              name="size"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Size</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                  >
                    <FormControl>
                      <SelectTrigger data-testid="size-select">
                        <SelectValue placeholder="Select a size" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {SIZES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Print size in inches (300 DPI, portrait)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
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
          </div>
          <FormField
            control={form.control}
            name="style_preset"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Style preset</FormLabel>
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <FormControl>
                    <SelectTrigger data-testid="preset-select">
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
          <div className="border-t border-border pt-8">
            <Button
              type="submit"
              size="lg"
              disabled={enqueue.isPending}
              className="w-full sm:w-auto"
            >
              {enqueue.isPending ? "Submitting…" : "Generate poster →"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
