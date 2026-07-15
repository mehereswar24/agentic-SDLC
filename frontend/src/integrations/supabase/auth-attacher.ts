import { createMiddleware } from "@tanstack/react-start";

export const attachSupabaseAuth = createMiddleware().server(async ({ next }) => {
  return await next();
});
