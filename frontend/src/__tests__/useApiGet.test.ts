import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useApiGet } from "../hooks/useApiGet";

// Mock the api module
vi.mock("../../api", () => ({
  apiGet: vi.fn(),
}));

import { apiGet } from "../../api";
const mockApiGet = vi.mocked(apiGet);

function makeResponse(body: unknown, ok = true, statusText = "OK"): Response {
  return {
    ok,
    statusText,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useApiGet", () => {
  it("fetches and returns data on success", async () => {
    mockApiGet.mockResolvedValue(makeResponse([1, 2, 3]));

    const { result } = renderHook(() =>
      useApiGet<number[]>("/api/test")
    );

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual([1, 2, 3]);
    expect(result.current.error).toBeNull();
  });

  it("applies transform to raw response", async () => {
    mockApiGet.mockResolvedValue(makeResponse({ items: [1, 2] }));

    const { result } = renderHook(() =>
      useApiGet<number[]>("/api/test", {
        transform: (raw) => (raw as { items: number[] }).items,
      })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual([1, 2]);
  });

  it("sets error state on non-ok response", async () => {
    mockApiGet.mockResolvedValue(makeResponse(null, false, "Not Found"));

    const { result } = renderHook(() => useApiGet<unknown>("/api/test"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toContain("Not Found");
  });

  it("sets error state on network failure", async () => {
    mockApiGet.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useApiGet<unknown>("/api/test"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Network error");
  });

  it("does not fetch when skip=true", () => {
    const { result } = renderHook(() =>
      useApiGet<unknown>("/api/test", { skip: true })
    );

    expect(mockApiGet).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("refetch triggers a new fetch", async () => {
    mockApiGet.mockResolvedValue(makeResponse("first"));

    const { result } = renderHook(() => useApiGet<string>("/api/test"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockApiGet).toHaveBeenCalledTimes(1);

    mockApiGet.mockResolvedValue(makeResponse("second"));
    act(() => result.current.refetch());

    await waitFor(() => expect(result.current.data).toBe("second"));
    expect(mockApiGet).toHaveBeenCalledTimes(2);
  });

  it("re-fetches when url changes", async () => {
    mockApiGet.mockResolvedValue(makeResponse("first"));

    const { result, rerender } = renderHook(
      ({ url }: { url: string }) => useApiGet<string>(url),
      { initialProps: { url: "/api/first" } }
    );

    await waitFor(() => expect(result.current.data).toBe("first"));
    expect(mockApiGet).toHaveBeenLastCalledWith("/api/first", expect.any(Object));

    mockApiGet.mockResolvedValue(makeResponse("second"));
    rerender({ url: "/api/second" });

    await waitFor(() => expect(result.current.data).toBe("second"));
    expect(mockApiGet).toHaveBeenLastCalledWith("/api/second", expect.any(Object));
  });
});
