// Plan 23-05 Task 2 — postcard creator page (PC-05).
//
// Mirrors frontend/src/pages/brochures/new.tsx but with discrete RHF fields
// (no JSON-paste) since PostcardCreateRequest is flat: headline + body +
// optional image_hint + brand_kit_slug + template + optional address_block.
//
// Editorial PageHeader uses number="08" + kicker="The Mail" — the
// PageHeader component composes the locked "08 / THE MAIL" string from
// these two pieces (CONTEXT.md kicker lock).
//
// Security (23-05 threat model T-23-17/T-23-18/T-23-19):
//   - Every form value renders as React JSX text (no dangerouslySetInnerHTML).
//   - Zod .strict() mirrors backend Pydantic extra="forbid".
//   - Address block .refine() requires all 3 fields when include_address=true,
//     mirroring the backend AddressBlock min_length=1 invariant.
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
import { Switch } from "@/components/ui/switch";
import {
  type ApiErrorBody,
  type PostcardCreateRequestBody,
  client,
} from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { PageHeader } from "@/components/PageHeader";

const SLUG = /^[a-z0-9][a-z0-9-]*$/;

// Mirrors flyer_generator/api/schemas/postcards.py::PostcardCreateRequest.
// `.strict()` mirrors Pydantic's extra="forbid". Do NOT use z.string().default()
// anywhere — zod v4's .default() breaks the RHF Resolver<T> generic-equality
// check (see plan 21-06 deviation #1). Seed defaults via useForm.defaultValues.
const PostcardFormSchema = z
  .object({
    headline: z.string().min(1, "headline is required").max(200),
    body: z.string().min(1, "body is required").max(2000),
    template: z.string().min(1).max(64),
    image_hint: z.string().max(500).optional(),
    brand_kit_slug: z
      .string()
      .regex(SLUG, "lowercase letters, digits, dashes")
      .max(64)
      .optional()
      .or(z.literal("")),
    include_address: z.boolean(),
    address_recipient_name: z.string().max(120).optional(),
    address_street: z.string().max(120).optional(),
    address_city_state_zip: z.string().max(120).optional(),
  })
  .strict()
  .refine(
    (v) =>
      !v.include_address ||
      (!!v.address_recipient_name &&
        !!v.address_street &&
        !!v.address_city_state_zip),
    {
      message: "all address fields required when address block is enabled",
      path: ["include_address"],
    },
  );

type PostcardFormValues = z.infer<typeof PostcardFormSchema>;

export function NewPostcardPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const form = useForm<PostcardFormValues>({
    resolver: zodResolver(PostcardFormSchema),
    defaultValues: {
      headline: "",
      body: "",
      template: "classic_portrait",
      image_hint: "",
      brand_kit_slug: "",
      include_address: false,
      address_recipient_name: "",
      address_street: "",
      address_city_state_zip: "",
    },
  });

  const enqueue = useMutation({
    mutationFn: async (values: PostcardFormValues) => {
      const body: PostcardCreateRequestBody = {
        headline: values.headline,
        body: values.body,
        template: values.template,
        image_hint: values.image_hint?.trim() ? values.image_hint : null,
        brand_kit_slug: values.brand_kit_slug?.trim()
          ? values.brand_kit_slug
          : null,
        address_block: values.include_address
          ? {
              recipient_name: values.address_recipient_name!,
              street: values.address_street!,
              city_state_zip: values.address_city_state_zip!,
            }
          : null,
      };
      const { data, error, response } = await client.POST(
        "/api/v1/postcards",
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
      toast.success(`Postcard enqueued (${job_id.slice(0, 8)}…)`);
      navigate(`/postcards/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const includeAddress = form.watch("include_address");

  return (
    <div className="mx-auto max-w-3xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="08"
        kicker="The Mail"
        title="New postcard"
        dek="Front-and-back direct mail. Headline over hero on the front; body and optional address block on the back. The pipeline ships a print-ready PDF alongside the two PNGs."
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
                  <Input placeholder="Save the date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="body"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Body</FormLabel>
                <FormControl>
                  <Textarea rows={6} {...field} />
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
                  <FormControl>
                    <Input placeholder="classic_portrait" {...field} />
                  </FormControl>
                  <FormDescription>
                    classic_portrait or modern_landscape
                  </FormDescription>
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
          <FormField
            control={form.control}
            name="image_hint"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Image hint (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="A field of poppies at dusk"
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
            name="include_address"
            render={({ field }) => (
              <FormItem className="flex items-center gap-3">
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormLabel className="!mt-0">
                  Include recipient address block
                </FormLabel>
                <FormMessage />
              </FormItem>
            )}
          />
          {includeAddress && (
            <div className="space-y-4 border-l-2 border-amber/30 pl-6">
              <FormField
                control={form.control}
                name="address_recipient_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Recipient name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Jane Doe"
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
                name="address_street"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Street</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="123 Main St"
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
                name="address_city_state_zip"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>City, state, zip</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Springfield, IL 62701"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          )}
          <div className="border-t border-border pt-8">
            <Button
              type="submit"
              size="lg"
              disabled={enqueue.isPending}
              className="w-full sm:w-auto"
            >
              {enqueue.isPending ? "Submitting…" : "Generate postcard →"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
