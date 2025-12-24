import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_ROUTES = [
  "/",
  "/auth/error",
  "/auth/pending",
  "/invite",
  "/api/auth",
];

// Routes that require specific roles (admin access)
const ADMIN_ROUTES = ["/admin"];

// Check if a path matches any of the public routes
function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => {
    if (route === "/") {
      return pathname === "/";
    }
    return pathname === route || pathname.startsWith(route + "/");
  });
}

// Check if a path is an admin route
function isAdminRoute(pathname: string): boolean {
  return ADMIN_ROUTES.some((route) => pathname.startsWith(route));
}

// Custom middleware that wraps NextAuth
export default withAuth(
  function middleware(req) {
    const { pathname } = req.nextUrl;
    const token = req.nextauth.token;

    // For admin routes, check if user has admin access
    if (isAdminRoute(pathname)) {
      const userRole = token?.role as string | undefined;
      const adminRoles = ["super_admin", "admin", "manager"];

      if (!userRole || !adminRoles.includes(userRole)) {
        // Redirect non-admin users to pre-session
        return NextResponse.redirect(new URL("/pre-session", req.url));
      }
    }

    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        const { pathname } = req.nextUrl;

        // Allow public routes without authentication
        if (isPublicRoute(pathname)) {
          return true;
        }

        // For all other routes, require a valid token
        return !!token;
      },
    },
    pages: {
      signIn: "/",
      error: "/auth/error",
    },
  }
);

// Configure which routes the middleware runs on
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
