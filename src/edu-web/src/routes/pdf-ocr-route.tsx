import { PdfOcrPage } from '@/features/pdf-ocr/pdf-ocr-page'
import { pdfOcrRoute } from '@/routes/_config'

export const PdfOcrRoute = () => {
  const params = pdfOcrRoute.useParams()
  return <PdfOcrPage projectId={params.projectId} />
}
