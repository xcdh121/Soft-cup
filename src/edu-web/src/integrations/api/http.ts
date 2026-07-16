import * as HttpClientRequest from '@effect/platform/HttpClientRequest'
import * as HttpClient from '@effect/platform/HttpClient'
import * as FetchHttpClient from '@effect/platform/FetchHttpClient'
import * as Effect from 'effect/Effect'
import { getAccessTokenEffect } from '@/lib/auth-client'
import * as ApiClient from '@/integrations/api/client'
import { NetworkMonitor } from '@/lib/network-monitor'

export class ApiClientService extends Effect.Service<ApiClientService>()(
  'ApiClientService',
  {
    dependencies: [FetchHttpClient.layer, NetworkMonitor.Default],
    scoped: Effect.gen(function* () {
      const client = yield* HttpClient.HttpClient

      const httpClient = client.pipe(
        HttpClient.mapRequestEffect(
          Effect.fn(function* (r) {
            const token = yield* getAccessTokenEffect
            return r.pipe(
              token
                ? HttpClientRequest.setHeader(
                    'Authorization',
                    `Bearer ${token}`,
                  )
                : (request) => request,
              HttpClientRequest.prependUrl(
                import.meta.env.VITE_SERVER_URL ?? window.location.origin,
              ),
            )
          }),
        ),
      )

      const apiClient = ApiClient.make(httpClient, {
        transformClient: Effect.fn(function* (c) {
          const token = yield* getAccessTokenEffect
          return token
            ? c.pipe(
                HttpClient.mapRequest((r) =>
                  r.pipe(
                    HttpClientRequest.setHeader(
                      'Authorization',
                      `Bearer ${token}`,
                    ),
                  ),
                ),
              )
            : c
        }),
      })

      return {
        httpClient,
        apiClient,
      }
    }),
  },
) {}
