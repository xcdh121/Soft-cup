import { ConfirmationDialog } from '@/components/confirmation-dialog'
import { EditChatDialog } from '@/features/chat/components/edit-chat-dialog'
import { UploadDocumentDialog } from '@/features/document/components/upload-document-dialog'
import { UpsertProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { ResourcePackageSheet } from '@/features/resource-package/components/resource-package-sheet'

export const ModalProvider = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <UpsertProjectDialog />
      <EditChatDialog />
      <UploadDocumentDialog />
      <ResourcePackageSheet />
      <ConfirmationDialog />
      {children}
    </>
  )
}
