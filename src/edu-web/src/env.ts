import { createEnv } from '@t3-oss/env-core'
import { z } from 'zod'

export const env = createEnv({
  server: {},
  clientPrefix: 'VITE_',
  client: {
    VITE_APP_TITLE: z.string().min(1).optional(),
    VITE_SERVER_URL: z.url().optional(),
    VITE_SUPABASE_URL: z.url().optional(),
    VITE_SUPABASE_ANON_KEY: z.string().min(1).optional(),
  },
  runtimeEnv: import.meta.env,
  emptyStringAsUndefined: true,
})
