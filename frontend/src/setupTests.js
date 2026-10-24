import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Com `globals: false` (vite.config.js) a Testing Library não regista sozinha
// a limpeza: sem isto, cada render fica no DOM e os testes seguintes
// encontram elementos duplicados.
afterEach(() => {
  cleanup();
});
