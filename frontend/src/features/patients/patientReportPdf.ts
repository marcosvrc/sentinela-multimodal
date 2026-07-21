/**
 * Exportacao em PDF da tela de paciente (botao "Gerar PDF"), incluindo
 * cabecalho com a marca do SentinelHealth, dados do paciente, alertas,
 * apoio a analise clinica (IA) e todos os paineis de observacao clinica
 * com seus graficos de serie temporal (sem paginacao - o chamador deve
 * passar o conteudo ja expandido/sem paginacao interna, ver
 * `ObservationTypePanel.showAllRows` e `AlertsPanel.printMode`).
 *
 * Abordagem: captura o DOM ja renderizado com `html2canvas` (rasteriza o
 * container inteiro, inclusive os graficos SVG do `recharts`) e distribui
 * a imagem resultante no espaco util de paginas A4 com `jspdf`, reservando
 * uma faixa fixa no topo (cabecalho de marca, so a partir da 2a pagina) e
 * uma faixa fixa no rodape (numeracao + aviso) desenhadas com primitivas
 * vetoriais do proprio `jspdf` - nao fazem parte da captura de tela.
 * Os dados do paciente aparecem como um bloco de texto vetorial logo
 * abaixo do cabecalho, apenas na primeira pagina.
 *
 * Preferido a montar o PDF inteiro "na mao" (texto + desenho vetorial)
 * porque replicaria toda a logica de layout/grafico ja existente na tela
 * sem trazer nenhum beneficio real neste caso (e um documento de apoio,
 * nao um relatorio formal como o de analise multimodal em
 * `app.reports.pdf`, que ja e gerado no backend a partir de dados
 * estruturados). Nunca chama o backend: e uma exportacao puramente do
 * que a tela ja carregou, sem nenhuma chamada de rede adicional.
 */
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

const A4_WIDTH_MM = 210;
const A4_HEIGHT_MM = 297;
const PAGE_MARGIN_MM = 10;
const HEADER_HEIGHT_MM = 22;
const PATIENT_INFO_HEIGHT_MM = 22;
const FOOTER_HEIGHT_MM = 10;

// Mesma paleta de marca de `frontend/src/styles/tokens.css`
// (`--color-primary-700`/`--color-text`/`--color-text-muted`) - jsPDF nao
// le variaveis CSS, entao os valores sao replicados aqui como RGB.
const BRAND_GREEN: [number, number, number] = [21, 112, 63];
const BRAND_GREEN_LIGHT: [number, number, number] = [231, 246, 236];
const TEXT_DARK: [number, number, number] = [26, 31, 39];
const TEXT_MUTED: [number, number, number] = [102, 112, 128];
const BORDER_COLOR: [number, number, number] = [226, 229, 233];

export interface PatientReportPdfMeta {
  patientName: string;
  medicalRecordNumber: string;
  ageLabel: string;
  registeredSex: string;
  heightLabel: string;
  bmiLabel: string;
}

/** Desenha o simbolo de marca do SentinelHealth (mesmo pulso/onda de sinal
 * vital do `Logo.tsx`, redesenhado com as primitivas vetoriais do jsPDF -
 * nao e possivel reaproveitar o SVG React diretamente aqui). */
function drawBrandMark(pdf: jsPDF, x: number, y: number, size: number) {
  pdf.setFillColor(...BRAND_GREEN_LIGHT);
  pdf.roundedRect(x, y, size, size, size * 0.25, size * 0.25, "F");

  pdf.setDrawColor(...BRAND_GREEN);
  pdf.setLineWidth(size * 0.09);
  pdf.setLineCap("round");
  const points: [number, number][] = [
    [x + size * 0.18, y + size * 0.53],
    [x + size * 0.31, y + size * 0.53],
    [x + size * 0.39, y + size * 0.34],
    [x + size * 0.53, y + size * 0.75],
    [x + size * 0.61, y + size * 0.44],
    [x + size * 0.82, y + size * 0.44],
  ];
  for (let i = 0; i < points.length - 1; i += 1) {
    pdf.line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1]);
  }
}

/** Cabecalho de marca, desenhado em toda pagina. */
function drawHeader(pdf: jsPDF) {
  const markSize = 10;
  drawBrandMark(pdf, PAGE_MARGIN_MM, PAGE_MARGIN_MM, markSize);

  pdf.setTextColor(...TEXT_DARK);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(15);
  pdf.text("SentinelHealth", PAGE_MARGIN_MM + markSize + 4, PAGE_MARGIN_MM + 5);

  pdf.setTextColor(...TEXT_MUTED);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    "Sistema de apoio a decisoes clinicas multimodais",
    PAGE_MARGIN_MM + markSize + 4,
    PAGE_MARGIN_MM + 10,
  );

  const generatedAt = new Date().toLocaleString("pt-BR");
  pdf.setFontSize(8);
  pdf.text(`Gerado em ${generatedAt}`, A4_WIDTH_MM - PAGE_MARGIN_MM, PAGE_MARGIN_MM + 5, {
    align: "right",
  });

  pdf.setDrawColor(...BORDER_COLOR);
  pdf.setLineWidth(0.3);
  pdf.line(
    PAGE_MARGIN_MM,
    PAGE_MARGIN_MM + HEADER_HEIGHT_MM,
    A4_WIDTH_MM - PAGE_MARGIN_MM,
    PAGE_MARGIN_MM + HEADER_HEIGHT_MM,
  );
}

/** Bloco de dados do paciente, desenhado apenas na primeira pagina. */
function drawPatientInfo(pdf: jsPDF, meta: PatientReportPdfMeta) {
  const top = PAGE_MARGIN_MM + HEADER_HEIGHT_MM + 4;
  const left = PAGE_MARGIN_MM;
  const width = A4_WIDTH_MM - PAGE_MARGIN_MM * 2;

  pdf.setTextColor(...TEXT_DARK);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(13);
  pdf.text(meta.patientName, left, top + 5);

  pdf.setTextColor(...TEXT_MUTED);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9.5);
  const fields = [
    `Prontuario: ${meta.medicalRecordNumber}`,
    `Idade: ${meta.ageLabel}`,
    `Sexo registrado: ${meta.registeredSex}`,
    `Altura: ${meta.heightLabel}`,
    `IMC: ${meta.bmiLabel}`,
  ];
  pdf.text(fields.join("   ·   "), left, top + 11, { maxWidth: width });

  pdf.setDrawColor(...BORDER_COLOR);
  pdf.setLineWidth(0.2);
  pdf.line(
    left,
    PAGE_MARGIN_MM + HEADER_HEIGHT_MM + PATIENT_INFO_HEIGHT_MM,
    A4_WIDTH_MM - PAGE_MARGIN_MM,
    PAGE_MARGIN_MM + HEADER_HEIGHT_MM + PATIENT_INFO_HEIGHT_MM,
  );
}

/** Rodape (numero de pagina + aviso de apoio a decisao), desenhado em
 * toda pagina - so pode ser chamado depois que todas as paginas ja
 * existirem (jsPDF nao permite saber o total de paginas antecipadamente
 * enquanto ainda esta adicionando conteudo). */
function drawFooter(pdf: jsPDF, pageNumber: number, totalPages: number) {
  const y = A4_HEIGHT_MM - PAGE_MARGIN_MM;
  pdf.setDrawColor(...BORDER_COLOR);
  pdf.setLineWidth(0.2);
  pdf.line(PAGE_MARGIN_MM, y - FOOTER_HEIGHT_MM + 3, A4_WIDTH_MM - PAGE_MARGIN_MM, y - FOOTER_HEIGHT_MM + 3);

  pdf.setTextColor(...TEXT_MUTED);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.text(
    "Documento de apoio a decisao clinica. Nao substitui a avaliacao do profissional responsavel.",
    PAGE_MARGIN_MM,
    y,
  );
  pdf.text(`Pagina ${pageNumber} de ${totalPages}`, A4_WIDTH_MM - PAGE_MARGIN_MM, y, {
    align: "right",
  });
}

/**
 * Renderiza `element` (deve estar completamente expandido/visivel e sem
 * paginacao interna no momento da chamada - o chamador e responsavel por
 * forcar a expansao de paineis colapsaveis e desativar paginacao de
 * tabelas antes de chamar esta funcao) em um PDF paginado com cabecalho
 * de marca, dados do paciente e rodape, e inicia o download no navegador.
 */
export async function exportElementToPdf(
  element: HTMLElement,
  meta: PatientReportPdfMeta,
): Promise<void> {
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    backgroundColor: "#ffffff",
  });

  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  pdf.setProperties({
    title: `Prontuario clinico - ${meta.patientName}`,
    subject: `SentinelHealth - prontuario ${meta.medicalRecordNumber}`,
  });

  const usableWidthMm = A4_WIDTH_MM - PAGE_MARGIN_MM * 2;
  const firstPageContentTopMm = PAGE_MARGIN_MM + HEADER_HEIGHT_MM + PATIENT_INFO_HEIGHT_MM + 4;
  const otherPageContentTopMm = PAGE_MARGIN_MM + HEADER_HEIGHT_MM + 4;
  const contentBottomMm = A4_HEIGHT_MM - PAGE_MARGIN_MM - FOOTER_HEIGHT_MM;

  const pixelsPerMm = canvas.width / usableWidthMm;
  let renderedHeightPx = 0;
  let pageNumber = 0;

  while (renderedHeightPx < canvas.height || pageNumber === 0) {
    const isFirstPage = pageNumber === 0;
    const contentTopMm = isFirstPage ? firstPageContentTopMm : otherPageContentTopMm;
    const availableHeightMm = contentBottomMm - contentTopMm;
    const sliceHeightPx = Math.min(
      availableHeightMm * pixelsPerMm,
      canvas.height - renderedHeightPx,
    );

    if (pageNumber > 0) pdf.addPage();
    drawHeader(pdf);
    if (isFirstPage) drawPatientInfo(pdf, meta);

    if (sliceHeightPx > 0) {
      const pageCanvas = document.createElement("canvas");
      pageCanvas.width = canvas.width;
      pageCanvas.height = sliceHeightPx;
      const pageContext = pageCanvas.getContext("2d");
      if (pageContext) {
        pageContext.drawImage(
          canvas,
          0,
          renderedHeightPx,
          canvas.width,
          sliceHeightPx,
          0,
          0,
          canvas.width,
          sliceHeightPx,
        );
        const sliceHeightMm = sliceHeightPx / pixelsPerMm;
        pdf.addImage(
          pageCanvas.toDataURL("image/png"),
          "PNG",
          PAGE_MARGIN_MM,
          contentTopMm,
          usableWidthMm,
          sliceHeightMm,
        );
      }
    }

    renderedHeightPx += sliceHeightPx;
    pageNumber += 1;

    // Guarda de seguranca: evita loop infinito se `sliceHeightPx` ficar
    // zerado por algum motivo inesperado (ex.: canvas vazio).
    if (sliceHeightPx <= 0 && renderedHeightPx < canvas.height) break;
  }

  const totalPages = pageNumber;
  for (let page = 1; page <= totalPages; page += 1) {
    pdf.setPage(page);
    drawFooter(pdf, page, totalPages);
  }

  const safeMrn = meta.medicalRecordNumber.replace(/[^a-zA-Z0-9-]/g, "");
  pdf.save(`paciente-${safeMrn || "sem-prontuario"}.pdf`);
}
