// Plan 21-05 Task 3 — replaces the plan-21-03 stub.
//
// Scrape-form page for /brand-kits/new. Uses react-hook-form + zod, mirroring
// the Pydantic shape of BrandKitFetchRequest exactly:
//   url: AnyHttpUrl
//   slug: ^[a-z0-9][a-z0-9-]*$, 1..64
// .strict() mirrors model_config = ConfigDict(extra="forbid").
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";

import { type ApiErrorBody, client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const SLUG = /^[a-z0-9][a-z0-9-]*$/;

// .strict() mirrors Pydantic's model_config = ConfigDict(extra="forbid"):
// unknown fields reject at validation time rather than leaking to the server.
const BrandKitFetchSchema = z
  .object({
    url: z.string().url(),
    slug: z
      .string()
      .min(1)
      .max(64)
      .regex(SLUG, "lowercase letters, digits, dashes"),
  })
  .strict();

type BrandKitFetchValues = z.infer<typeof BrandKitFetchSchema>;

export function ScrapeBrandKitPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const form = useForm<BrandKitFetchValues>({
    resolver: zodResolver(BrandKitFetchSchema),
    defaultValues: { url: "", slug: "" },
  });

  const enqueue = useMutation({
    mutationFn: async (body: BrandKitFetchValues) => {
      const { data, error, response } = await client.POST(
        "/api/v1/brand-kits/fetch",
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
      queryClient.invalidateQueries({ queryKey: queryKeys.brandKits() });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      toast.success(`Scrape enqueued (${job_id.slice(0, 8)}...)`);
      navigate(`/jobs/${job_id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Scrape a brand kit</h1>
      <p className="text-muted-foreground text-sm">
        Provide a website URL and a unique slug. Phase 18&rsquo;s scraper
        extracts palette, typography, logos, and voice into{" "}
        <code>.brand-kits/&lt;slug&gt;/</code>.
      </p>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => enqueue.mutate(values))}
          className="space-y-4"
          noValidate
        >
          <FormField
            control={form.control}
            name="url"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Source URL</FormLabel>
                <FormControl>
                  <Input
                    type="url"
                    placeholder="https://example.com"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="slug"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Slug</FormLabel>
                <FormControl>
                  <Input placeholder="example-co" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" disabled={enqueue.isPending}>
            {enqueue.isPending ? "Submitting..." : "Scrape"}
          </Button>
        </form>
      </Form>
    </div>
  );
}
