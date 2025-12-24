"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { validateInvitation } from "@/lib/auth-db";
import type { Invitation } from "@/types/auth";
import { ROLE_DEFINITIONS } from "@/types/auth";

export default function InvitePage() {
  const params = useParams();
  const router = useRouter();
  const code = params.code as string;

  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function checkInvitation() {
      if (!code) {
        setError("Invalid invitation link");
        setIsLoading(false);
        return;
      }

      try {
        const inv = await validateInvitation(code);
        if (inv) {
          setInvitation(inv);
        } else {
          setError("This invitation link is invalid, expired, or has reached its maximum uses.");
        }
      } catch (err) {
        console.error("Error validating invitation:", err);
        setError("Failed to validate invitation. Please try again.");
      }
      setIsLoading(false);
    }

    checkInvitation();
  }, [code]);

  const handleContinue = () => {
    // Store the invitation code in session storage and redirect to SSO login
    if (typeof window !== "undefined") {
      sessionStorage.setItem("pulse_invite_code", code);
    }
    // Redirect to the main login page where they'll use SSO
    router.push("/");
  };

  if (isLoading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-gray-300 border-t-black rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">Validating invitation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 text-red-600 mb-6">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-3">Invalid Invitation</h1>
          <p className="text-gray-600 mb-8">{error}</p>

          <div className="space-y-3">
            <button
              onClick={() => router.push("/")}
              className="block w-full py-3 px-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
            >
              Go to Sign In
            </button>
            <a
              href="mailto:support@sleepnumber.com?subject=PULSE%20Training%20Invitation%20Issue"
              className="block w-full py-3 px-4 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
            >
              Contact Support
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-black text-white text-2xl font-bold mb-4">
            P
          </div>
          <h1 className="text-3xl font-bold text-gray-900">PULSE Training</h1>
          <p className="mt-2 text-gray-600">Sales Behavioral Certification Platform</p>
        </div>

        {/* Invitation Card */}
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-8">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 text-green-600 mb-4">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold">You&apos;re Invited!</h2>
            <p className="text-gray-600 mt-2">
              You&apos;ve been invited to join PULSE Training
            </p>
          </div>

          {/* Invitation Details */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Role:</span>
              <span className="font-medium">
                {invitation && ROLE_DEFINITIONS[invitation.role]?.name}
              </span>
            </div>
            {invitation?.requiresApproval && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Approval:</span>
                <span className="font-medium text-yellow-600">Admin approval required</span>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Expires:</span>
              <span className="font-medium">
                {invitation && new Date(invitation.expiresAt).toLocaleDateString()}
              </span>
            </div>
          </div>

          {invitation?.requiresApproval && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
              <div className="flex items-start gap-2">
                <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm text-yellow-700">
                  After signing in, an administrator will review and approve your access request.
                </p>
              </div>
            </div>
          )}

          <button
            onClick={handleContinue}
            className="w-full py-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors flex items-center justify-center gap-3"
          >
            <svg className="w-5 h-5" viewBox="0 0 21 21" fill="currentColor">
              <path d="M0 0h10v10H0V0zm11 0h10v10H11V0zM0 11h10v10H0V11zm11 0h10v10H11V11z"/>
            </svg>
            Continue with Microsoft
          </button>

          <p className="mt-4 text-center text-sm text-gray-500">
            Use your Sleep Number corporate credentials
          </p>
        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-sm text-gray-500">
          PULSE Selling Methodology Training Platform
        </p>
      </div>
    </div>
  );
}
