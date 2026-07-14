import { createEnv } from '@t3-oss/env-core'
import { z } from 'zod'

export const env = createEnv({
  server: {},
  clientPrefix: 'VITE_',
  client: {
    VITE_APP_TITLE: z.string().min(1).optional(),
    VITE_SERVER_URL: z.url().optional(),
    VITE_AVATAR_SERVER_URL: z.url().optional(),
    VITE_AVATAR_APP_ID: z.string().min(1).optional(),
    VITE_AVATAR_API_KEY: z.string().min(1).optional(),
    VITE_AVATAR_API_SECRET: z.string().min(1).optional(),
    VITE_AVATAR_SCENE_ID: z.string().min(1).optional(),
    VITE_AVATAR_ID: z.string().min(1).optional(),
    VITE_AVATAR_VCN: z.string().min(1).optional(),
  },
  runtimeEnv: import.meta.env,
  emptyStringAsUndefined: true,
})
