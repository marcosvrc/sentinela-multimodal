import { describe, expect, it } from "vitest";
import { AnalysisStatus, ANALYSIS_STATUS_TRANSITIONS } from "../src/types/enums.generated";

describe("enums.generated (gerado a partir de backend/app/core/enums.py)", () => {
  it("expoe todos os estados da analise", () => {
    expect(AnalysisStatus.CREATED).toBe("CREATED");
    expect(AnalysisStatus.COMPLETED).toBe("COMPLETED");
    expect(AnalysisStatus.CANCELLED).toBe("CANCELLED");
  });

  it("marca estados terminais sem transicoes de saida", () => {
    expect(ANALYSIS_STATUS_TRANSITIONS[AnalysisStatus.COMPLETED]).toEqual([]);
    expect(ANALYSIS_STATUS_TRANSITIONS[AnalysisStatus.FAILED_FINAL]).toEqual([]);
    expect(ANALYSIS_STATUS_TRANSITIONS[AnalysisStatus.CANCELLED]).toEqual([]);
  });

  it("nao permite transicao direta de CREATED para COMPLETED", () => {
    const allowed = ANALYSIS_STATUS_TRANSITIONS[AnalysisStatus.CREATED];
    expect(allowed).not.toContain(AnalysisStatus.COMPLETED);
    expect(allowed).toContain(AnalysisStatus.UPLOADING);
  });
});
