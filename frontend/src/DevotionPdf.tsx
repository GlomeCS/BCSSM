import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import Navbar from "./Navbar";
import { useRequireAuth } from "./hooks/useRequireAuth";
import "./DevotionPdf.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const PDF_URL = `${import.meta.env.BASE_URL}pdfs/team-devotion-live-in-the-light.pdf`;
const PAGE_WIDTH = 760;

export default function DevotionPdf() {
  const { loading: authLoading } = useRequireAuth();
  const [numPages, setNumPages] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (authLoading) {
    return (
      <>
        <Navbar />
        <div className="devotion-pdf-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="devotion-pdf-page">
        <header className="page-header">
          <div className="page-header-content">
            <h1 className="page-title">Team Devotional Resource</h1>
            <p className="page-subtitle">Live in the Light</p>
          </div>
        </header>

        <section className="pdf-viewer-section">
          {error && <p className="pdf-error">{error}</p>}
          <Document
            file={PDF_URL}
            onLoadSuccess={({ numPages }) => setNumPages(numPages)}
            onLoadError={() => setError("Unable to load the devotion PDF. Please try again later.")}
            loading={
              <div className="loading-container">
                <div className="loading-spinner"></div>
              </div>
            }
            className="pdf-document"
          >
            {numPages &&
              Array.from({ length: numPages }, (_, i) => (
                <Page
                  key={i + 1}
                  pageNumber={i + 1}
                  width={PAGE_WIDTH}
                  className="pdf-page"
                  renderAnnotationLayer={false}
                />
              ))}
          </Document>
        </section>
      </div>
    </>
  );
}
