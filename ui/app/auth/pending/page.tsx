"use client";

import Link from "next/link";

export default function PendingApprovalPage() {
  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-yellow-100 text-yellow-600 mb-6">
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-3">Approval Pending</h1>
        <p className="text-gray-600 mb-8">
          Your account is awaiting administrator approval. You&apos;ll receive an email once your access
          has been granted.
        </p>

        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-8">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="text-left">
              <h3 className="font-medium text-yellow-900">What happens next?</h3>
              <p className="text-sm text-yellow-700 mt-1">
                An administrator will review your request and either approve or deny access.
                This typically takes 1-2 business days.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <Link
            href="/"
            className="block w-full py-3 px-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
          >
            Back to Sign In
          </Link>
          <a
            href="mailto:support@sleepnumber.com?subject=PULSE%20Training%20Approval%20Request"
            className="block w-full py-3 px-4 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
          >
            Contact Administrator
          </a>
        </div>
      </div>
    </div>
  );
}
