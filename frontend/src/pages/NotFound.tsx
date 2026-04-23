import { Link, useLocation } from "react-router";

export function NotFoundPage() {
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center p-6">
      <h1 className="mb-2 text-2xl font-semibold">Not found</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        No route matches <code className="rounded bg-muted px-1">{pathname}</code>.
      </p>
      <Link to="/" className="text-sm underline">
        Back to home
      </Link>
    </div>
  );
}
