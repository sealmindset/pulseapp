"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

function AuthErrorContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  const errorMessages: Record<string, { title: string; message: string }> = {
    AccessDenied: {
      title: "Access Denied",
      message:
        "You don't have permission to access PULSE Training. Please contact your administrator to request access.",
    },
    AccountDisabled: {
      title: "Account Disabled",
      message:
        "Your account has been disabled. Please contact your administrator if you believe this is an error.",
    },
    NoInvitation: {
      title: "No Invitation Found",
      message:
        "You need an invitation to access PULSE Training. Please contact your administrator to request an invite.",
    },
    Configuration: {
      title: "Configuration Error",
      message: "There's an issue with the authentication configuration. Please contact support.",
    },
    Default: {
      title: "Authentication Error",
      message: "An error occurred during sign-in. Please try again or contact support.",
    },
  };

  const errorInfo = errorMessages[error || "Default"] || errorMessages.Default;

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 text-red-600 mb-6">
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-3">{errorInfo.title}</h1>
        <p className="text-gray-600 mb-8">{errorInfo.message}</p>

        <div className="space-y-3">
          <Link
            href="/"
            className="block w-full py-3 px-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
          >
            Back to Sign In
          </Link>
          <a
            href="mailto:support@sleepnumber.com?subject=PULSE%20Training%20Access%20Request"
            className="block w-full py-3 px-4 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
          >
            Contact Support
          </a>
        </div>

        {error && (
          <p className="mt-6 text-xs text-gray-400">
            Error code: {error}
          </p>
        )}
      </div>
    </div>
  );
}

export default function AuthErrorPage() {
  return (
    <Suspense fallback={<div className="min-h-[80vh] flex items-center justify-center">Loading...</div>}>
      <AuthErrorContent />
    </Suspense>
  );
}
