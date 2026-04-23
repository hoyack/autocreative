import "./index.css";
import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <div className="p-6 font-sans">
      <h1 className="text-2xl font-semibold">flyer-generator</h1>
      <p className="text-sm text-muted-foreground">
        Frontend scaffold ready. Routing + data layer land in plans 21-02 / 21-03 / 21-04.
      </p>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
