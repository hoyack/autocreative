import "./index.css";
import React from "react";
import { createRoot } from "react-dom/client";
import { Button } from "@/components/ui/button";

function App() {
  return (
    <div className="p-6 font-sans">
      <h1 className="mb-4 text-2xl font-semibold">flyer-generator</h1>
      <p className="mb-4 text-sm text-muted-foreground">Scaffold smoke test.</p>
      <Button>If you see this styled, ShadCN + Tailwind v4 works.</Button>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
