import { setupServer } from 'msw/node'

// Handlers are added per test with `server.use(...)`; unhandled requests fail the test.
export const server = setupServer()
