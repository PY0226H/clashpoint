import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppRoot } from "@echoisle/app-shell";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppRoot />
  </StrictMode>
);
