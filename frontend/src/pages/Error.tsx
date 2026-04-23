import { isRouteErrorResponse, useRouteError, Link } from "react-router";

export function ErrorPage() {
  const error = useRouteError();
  let title = "Something went wrong";
  let detail: string | null = null;
  if (isRouteErrorResponse(error)) {
    title = `${error.status} ${error.statusText}`;
    detail = typeof error.data === "string" ? error.data : null;
  } else if (error instanceof Error) {
    detail = error.message;
  }
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 font-sans">
      <h1 className="mb-2 text-2xl font-semibold">{title}</h1>
      {detail && (
        <p className="mb-4 max-w-xl text-sm text-muted-foreground">{detail}</p>
      )}
      <Link to="/" className="text-sm underline">
        Back to home
      </Link>
    </div>
  );
}
