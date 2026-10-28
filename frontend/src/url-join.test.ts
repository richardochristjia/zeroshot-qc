import { afterEach, describe, expect, it, vi } from "vitest";
import { normalizeApiBase, referenceImageUrl, resolveFileUrl } from "./api.ts";

describe("normalizeApiBase", () => {
  it("strips a single trailing slash", () => {
    expect(normalizeApiBase("http://localhost:8000/")).toBe(
      "http://localhost:8000",
    );
  });

  it("strips repeated trailing slashes", () => {
    expect(normalizeApiBase("http://localhost:8000///")).toBe(
      "http://localhost:8000",
    );
  });

  it("leaves slash-free bases untouched", () => {
    expect(normalizeApiBase("http://localhost:8000")).toBe(
      "http://localhost:8000",
    );
  });

  it("maps empty, unset, and non-string bases to empty", () => {
    expect(normalizeApiBase("")).toBe("");
    expect(normalizeApiBase(undefined)).toBe("");
    expect(normalizeApiBase(42)).toBe("");
  });
});

describe("resolveFileUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("passes absolute and object URLs through untouched", () => {
    expect(resolveFileUrl("blob:http://localhost:5173/abc")).toBe(
      "blob:http://localhost:5173/abc",
    );
    expect(resolveFileUrl("data:image/png;base64,iVBOR")).toBe(
      "data:image/png;base64,iVBOR",
    );
    expect(resolveFileUrl("http://cdn.example/x.png")).toBe(
      "http://cdn.example/x.png",
    );
    expect(resolveFileUrl("https://cdn.example/x.png")).toBe(
      "https://cdn.example/x.png",
    );
  });

  it("joins server-relative URLs without double slashes", async () => {
    vi.stubEnv("VITE_API_URL", "http://localhost:8000/");
    const mod = await import("./api.ts");
    expect(mod.resolveFileUrl("/files/a.png")).toBe(
      "http://localhost:8000/files/a.png",
    );
  });

  it("keeps relative URLs relative when the base is empty (dev proxy)", async () => {
    vi.stubEnv("VITE_API_URL", "");
    const mod = await import("./api.ts");
    expect(mod.resolveFileUrl("/files/a.png")).toBe("/files/a.png");
  });
});

describe("referenceImageUrl", () => {
  it("maps a data-relative path to the /files route", () => {
    expect(referenceImageUrl("mvtec/a.png")).toBe(
      resolveFileUrl("/files/mvtec/a.png"),
    );
    expect(referenceImageUrl("mvtec/a.png")).toMatch(/\/files\/mvtec\/a\.png$/);
  });
});
