# PULSE Input Validation Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** MEDIUM
**Related Documents:** [securedbydesign.md](securedbydesign.md), [promptsecurity.md](promptsecurity.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Input Validation Principles](#input-validation-principles)
3. [Validation Library Setup (Zod)](#validation-library-setup-zod)
4. [API Request Validation](#api-request-validation)
5. [Form Input Validation](#form-input-validation)
6. [File Upload Validation](#file-upload-validation)
7. [Output Encoding](#output-encoding)
8. [Database Input Sanitization](#database-input-sanitization)
9. [Common Attack Prevention](#common-attack-prevention)
10. [Testing and Validation](#testing-and-validation)
11. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Input validation is a critical security control that protects against:

- **Injection attacks** (SQL, NoSQL, Command, LDAP)
- **Cross-Site Scripting (XSS)**
- **Path Traversal**
- **Buffer Overflow**
- **Business Logic Bypass**
- **Data Corruption**

This guide implements comprehensive input validation using Zod for type-safe schema validation across the PULSE application.

---

## Input Validation Principles

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Client-Side Validation                          │
│           (UX improvement, not security - can be bypassed)               │
├─────────────────────────────────────────────────────────────────────────┤
│                         API Layer Validation                             │
│      (Schema validation, type checking, format validation)               │
├─────────────────────────────────────────────────────────────────────────┤
│                       Business Logic Validation                          │
│    (Authorization, business rules, cross-field validation)               │
├─────────────────────────────────────────────────────────────────────────┤
│                        Database Layer Validation                         │
│         (Constraints, triggers, parameterized queries)                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Validation Rules

| Principle | Description |
|-----------|-------------|
| Allowlist | Accept only known-good input |
| Deny by Default | Reject anything not explicitly allowed |
| Type Enforcement | Validate data types strictly |
| Length Limits | Enforce minimum and maximum lengths |
| Format Validation | Use regex for structured data |
| Encoding | Encode output for the context |
| Canonicalization | Normalize before validation |

---

## Validation Library Setup (Zod)

### Installation

```bash
npm install zod
```

### Create Validation Utilities

Create `ui/lib/validation/index.ts`:

```typescript
/**
 * PULSE Validation Utilities
 * Centralized input validation using Zod
 */

import { z } from 'zod';

// Re-export Zod for convenience
export { z } from 'zod';

// Common validation patterns
export const patterns = {
  // Email - stricter than default
  email: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,

  // UUID v4
  uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,

  // Safe filename (no path traversal)
  safeFilename: /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/,

  // URL-safe slug
  slug: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,

  // Alphanumeric only
  alphanumeric: /^[a-zA-Z0-9]+$/,

  // No special characters (for names)
  safeName: /^[a-zA-Z\s'-]+$/,

  // ISO 8601 date
  isoDate: /^\d{4}-\d{2}-\d{2}$/,

  // Phone number (international)
  phone: /^\+?[1-9]\d{1,14}$/,
};

// Reusable schema components
export const schemas = {
  // Safe string (no dangerous characters)
  safeString: z.string()
    .transform(s => s.trim())
    .refine(s => !/<script|javascript:|data:/i.test(s), {
      message: 'String contains potentially dangerous content',
    }),

  // Email
  email: z.string()
    .email('Invalid email address')
    .toLowerCase()
    .max(254, 'Email too long'),

  // UUID
  uuid: z.string()
    .regex(patterns.uuid, 'Invalid UUID format'),

  // Non-empty string with max length
  nonEmptyString: (maxLength: number = 1000) =>
    z.string()
      .min(1, 'This field is required')
      .max(maxLength, `Maximum ${maxLength} characters allowed`)
      .transform(s => s.trim()),

  // Optional string with max length
  optionalString: (maxLength: number = 1000) =>
    z.string()
      .max(maxLength, `Maximum ${maxLength} characters allowed`)
      .transform(s => s.trim())
      .optional(),

  // Positive integer
  positiveInt: z.number()
    .int('Must be an integer')
    .positive('Must be a positive number'),

  // Pagination
  pagination: z.object({
    page: z.number().int().min(1).default(1),
    limit: z.number().int().min(1).max(100).default(20),
  }),

  // Date range
  dateRange: z.object({
    startDate: z.string().regex(patterns.isoDate).optional(),
    endDate: z.string().regex(patterns.isoDate).optional(),
  }).refine(
    data => {
      if (data.startDate && data.endDate) {
        return new Date(data.startDate) <= new Date(data.endDate);
      }
      return true;
    },
    { message: 'Start date must be before end date' }
  ),
};

// Sanitization functions
export const sanitize = {
  /**
   * Remove HTML tags
   */
  stripHtml: (input: string): string => {
    return input.replace(/<[^>]*>/g, '');
  },

  /**
   * Escape HTML entities
   */
  escapeHtml: (input: string): string => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#x27;',
      '/': '&#x2F;',
    };
    return input.replace(/[&<>"'/]/g, char => entities[char]);
  },

  /**
   * Remove null bytes and control characters
   */
  removeControlChars: (input: string): string => {
    return input.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
  },

  /**
   * Normalize unicode (prevent homograph attacks)
   */
  normalizeUnicode: (input: string): string => {
    return input.normalize('NFKC');
  },

  /**
   * Full sanitization pipeline
   */
  full: (input: string): string => {
    let result = input;
    result = sanitize.removeControlChars(result);
    result = sanitize.normalizeUnicode(result);
    result = result.trim();
    return result;
  },
};

// Validation error formatter
export function formatZodError(error: z.ZodError): Record<string, string> {
  const formatted: Record<string, string> = {};

  for (const issue of error.issues) {
    const path = issue.path.join('.');
    if (!formatted[path]) {
      formatted[path] = issue.message;
    }
  }

  return formatted;
}

// Validation result type
export type ValidationResult<T> =
  | { success: true; data: T }
  | { success: false; errors: Record<string, string> };

// Safe parse wrapper
export function validateData<T>(
  schema: z.ZodSchema<T>,
  data: unknown
): ValidationResult<T> {
  const result = schema.safeParse(data);

  if (result.success) {
    return { success: true, data: result.data };
  }

  return {
    success: false,
    errors: formatZodError(result.error),
  };
}
```

---

## API Request Validation

### Create Request Validation Middleware

Create `ui/lib/validation/api-validator.ts`:

```typescript
/**
 * PULSE API Request Validator
 * Middleware for validating API requests
 */

import { NextRequest, NextResponse } from 'next/server';
import { z, ZodSchema } from 'zod';
import { formatZodError, sanitize } from './index';
import { logSecurityEvent } from '../security-logger';

export interface ValidationOptions {
  body?: ZodSchema;
  query?: ZodSchema;
  params?: ZodSchema;
  sanitizeStrings?: boolean;
  logValidationFailures?: boolean;
}

export interface ValidatedRequest<TBody = any, TQuery = any, TParams = any> {
  body: TBody;
  query: TQuery;
  params: TParams;
}

/**
 * Recursively sanitize string values in an object
 */
function sanitizeObject(obj: any): any {
  if (typeof obj === 'string') {
    return sanitize.full(obj);
  }

  if (Array.isArray(obj)) {
    return obj.map(sanitizeObject);
  }

  if (obj && typeof obj === 'object') {
    const result: Record<string, any> = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = sanitizeObject(value);
    }
    return result;
  }

  return obj;
}

/**
 * Extract query parameters from request
 */
function extractQueryParams(request: NextRequest): Record<string, any> {
  const params: Record<string, any> = {};

  request.nextUrl.searchParams.forEach((value, key) => {
    // Handle arrays (e.g., ?tags=a&tags=b)
    if (params[key]) {
      if (Array.isArray(params[key])) {
        params[key].push(value);
      } else {
        params[key] = [params[key], value];
      }
    } else {
      params[key] = value;
    }
  });

  return params;
}

/**
 * Create validation error response
 */
function createValidationErrorResponse(
  errors: Record<string, string>,
  location: string
): NextResponse {
  return NextResponse.json(
    {
      error: 'Validation failed',
      code: 'VALIDATION_ERROR',
      location,
      details: errors,
    },
    { status: 400 }
  );
}

/**
 * Validate API request middleware
 */
export async function validateRequest<
  TBody = any,
  TQuery = any,
  TParams = any
>(
  request: NextRequest,
  options: ValidationOptions,
  handler: (
    request: NextRequest,
    validated: ValidatedRequest<TBody, TQuery, TParams>
  ) => Promise<NextResponse>
): Promise<NextResponse> {
  const validated: ValidatedRequest<TBody, TQuery, TParams> = {
    body: {} as TBody,
    query: {} as TQuery,
    params: {} as TParams,
  };

  // Validate body
  if (options.body) {
    try {
      let body = await request.json();

      if (options.sanitizeStrings !== false) {
        body = sanitizeObject(body);
      }

      const result = options.body.safeParse(body);

      if (!result.success) {
        if (options.logValidationFailures) {
          await logSecurityEvent({
            type: 'VALIDATION_FAILED',
            clientId: request.headers.get('x-user-id') || 'unknown',
            path: request.nextUrl.pathname,
            timestamp: new Date().toISOString(),
            details: {
              location: 'body',
              errors: formatZodError(result.error),
            },
          });
        }

        return createValidationErrorResponse(
          formatZodError(result.error),
          'body'
        );
      }

      validated.body = result.data;
    } catch (error) {
      return NextResponse.json(
        {
          error: 'Invalid JSON in request body',
          code: 'INVALID_JSON',
        },
        { status: 400 }
      );
    }
  }

  // Validate query parameters
  if (options.query) {
    let query = extractQueryParams(request);

    if (options.sanitizeStrings !== false) {
      query = sanitizeObject(query);
    }

    const result = options.query.safeParse(query);

    if (!result.success) {
      if (options.logValidationFailures) {
        await logSecurityEvent({
          type: 'VALIDATION_FAILED',
          clientId: request.headers.get('x-user-id') || 'unknown',
          path: request.nextUrl.pathname,
          timestamp: new Date().toISOString(),
          details: {
            location: 'query',
            errors: formatZodError(result.error),
          },
        });
      }

      return createValidationErrorResponse(
        formatZodError(result.error),
        'query'
      );
    }

    validated.query = result.data;
  }

  // Validate URL params (if provided)
  if (options.params) {
    // Params are typically extracted from the route
    // This is a placeholder for dynamic route validation
    const result = options.params.safeParse({});

    if (!result.success) {
      return createValidationErrorResponse(
        formatZodError(result.error),
        'params'
      );
    }

    validated.params = result.data;
  }

  return handler(request, validated);
}

/**
 * Higher-order function to wrap handlers with validation
 */
export function withValidation<TBody = any, TQuery = any, TParams = any>(
  options: ValidationOptions,
  handler: (
    request: NextRequest,
    validated: ValidatedRequest<TBody, TQuery, TParams>
  ) => Promise<NextResponse>
) {
  return async (request: NextRequest): Promise<NextResponse> => {
    return validateRequest(request, options, handler);
  };
}
```

### Define API Schemas

Create `ui/lib/validation/schemas/chat.ts`:

```typescript
/**
 * PULSE Chat API Validation Schemas
 */

import { z } from 'zod';
import { schemas } from '../index';

// Chat message schema
export const chatMessageSchema = z.object({
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string()
    .min(1, 'Message cannot be empty')
    .max(32000, 'Message too long (max 32000 characters)')
    .transform(s => s.trim()),
});

// Chat request schema
export const chatRequestSchema = z.object({
  message: z.string()
    .min(1, 'Message cannot be empty')
    .max(8000, 'Message too long (max 8000 characters)')
    .transform(s => s.trim()),

  conversationId: schemas.uuid.optional(),

  messages: z.array(chatMessageSchema)
    .max(50, 'Too many messages in history')
    .optional(),

  temperature: z.number()
    .min(0, 'Temperature must be between 0 and 2')
    .max(2, 'Temperature must be between 0 and 2')
    .optional(),

  maxTokens: z.number()
    .int()
    .min(1)
    .max(4000)
    .optional(),
});

export type ChatRequest = z.infer<typeof chatRequestSchema>;

// Chat response schema (for validation)
export const chatResponseSchema = z.object({
  message: z.string(),
  conversationId: schemas.uuid,
  usage: z.object({
    promptTokens: z.number(),
    completionTokens: z.number(),
    totalTokens: z.number(),
  }).optional(),
});
```

Create `ui/lib/validation/schemas/user.ts`:

```typescript
/**
 * PULSE User Validation Schemas
 */

import { z } from 'zod';
import { schemas, patterns } from '../index';

// User profile update schema
export const userProfileUpdateSchema = z.object({
  name: z.string()
    .min(1, 'Name is required')
    .max(100, 'Name too long')
    .regex(patterns.safeName, 'Name contains invalid characters')
    .optional(),

  email: schemas.email.optional(),

  timezone: z.string()
    .max(50)
    .optional(),

  language: z.enum(['en', 'es', 'fr', 'de', 'ja', 'zh'])
    .optional(),

  preferences: z.object({
    theme: z.enum(['light', 'dark', 'system']).optional(),
    notifications: z.boolean().optional(),
    emailDigest: z.enum(['daily', 'weekly', 'never']).optional(),
  }).optional(),
});

export type UserProfileUpdate = z.infer<typeof userProfileUpdateSchema>;

// Password change schema
export const passwordChangeSchema = z.object({
  currentPassword: z.string()
    .min(1, 'Current password is required'),

  newPassword: z.string()
    .min(12, 'Password must be at least 12 characters')
    .max(128, 'Password too long')
    .regex(/[A-Z]/, 'Password must contain uppercase letter')
    .regex(/[a-z]/, 'Password must contain lowercase letter')
    .regex(/[0-9]/, 'Password must contain number')
    .regex(/[^A-Za-z0-9]/, 'Password must contain special character'),

  confirmPassword: z.string(),
}).refine(data => data.newPassword === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
}).refine(data => data.newPassword !== data.currentPassword, {
  message: 'New password must be different from current password',
  path: ['newPassword'],
});

export type PasswordChange = z.infer<typeof passwordChangeSchema>;
```

### Apply Validation to API Routes

Update `ui/app/api/chat/route.ts`:

```typescript
/**
 * PULSE Chat API with Validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { withValidation, ValidatedRequest } from '@/lib/validation/api-validator';
import { chatRequestSchema, ChatRequest } from '@/lib/validation/schemas/chat';
import { withRateLimit } from '@/lib/rate-limit-middleware';
import { withPromptSecurity } from '@/lib/prompt-security-middleware';

async function handleChat(
  request: NextRequest,
  validated: ValidatedRequest<ChatRequest>
): Promise<NextResponse> {
  const { message, conversationId, messages, temperature, maxTokens } = validated.body;

  // Your chat implementation here...

  return NextResponse.json({
    message: 'Response from AI',
    conversationId: conversationId || 'new-id',
  });
}

// Apply all middleware
const validatedHandler = withValidation(
  {
    body: chatRequestSchema,
    logValidationFailures: true,
  },
  handleChat
);

export const POST = withRateLimit('chat', validatedHandler);
```

---

## Form Input Validation

### React Form Validation Hook

Create `ui/hooks/useFormValidation.ts`:

```typescript
/**
 * PULSE Form Validation Hook
 */

import { useState, useCallback } from 'react';
import { z, ZodSchema } from 'zod';
import { formatZodError } from '@/lib/validation';

export interface UseFormValidationOptions<T> {
  schema: ZodSchema<T>;
  initialValues?: Partial<T>;
  onSubmit: (data: T) => Promise<void> | void;
}

export interface FormState<T> {
  values: Partial<T>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  isSubmitting: boolean;
  isValid: boolean;
}

export function useFormValidation<T extends Record<string, any>>({
  schema,
  initialValues = {},
  onSubmit,
}: UseFormValidationOptions<T>) {
  const [values, setValues] = useState<Partial<T>>(initialValues);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateField = useCallback(
    (name: string, value: any): string | null => {
      try {
        // Create a partial schema for single field validation
        const partialData = { ...values, [name]: value };
        schema.parse(partialData);
        return null;
      } catch (error) {
        if (error instanceof z.ZodError) {
          const fieldError = error.issues.find(
            issue => issue.path[0] === name
          );
          return fieldError?.message || null;
        }
        return null;
      }
    },
    [schema, values]
  );

  const validateAll = useCallback((): boolean => {
    const result = schema.safeParse(values);

    if (result.success) {
      setErrors({});
      return true;
    }

    setErrors(formatZodError(result.error));
    return false;
  }, [schema, values]);

  const handleChange = useCallback(
    (name: string, value: any) => {
      setValues(prev => ({ ...prev, [name]: value }));

      // Validate on change if field was touched
      if (touched[name]) {
        const error = validateField(name, value);
        setErrors(prev => {
          if (error) {
            return { ...prev, [name]: error };
          }
          const { [name]: _, ...rest } = prev;
          return rest;
        });
      }
    },
    [touched, validateField]
  );

  const handleBlur = useCallback(
    (name: string) => {
      setTouched(prev => ({ ...prev, [name]: true }));

      const error = validateField(name, values[name]);
      setErrors(prev => {
        if (error) {
          return { ...prev, [name]: error };
        }
        const { [name]: _, ...rest } = prev;
        return rest;
      });
    },
    [values, validateField]
  );

  const handleSubmit = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();

      // Mark all fields as touched
      const allTouched = Object.keys(values).reduce(
        (acc, key) => ({ ...acc, [key]: true }),
        {}
      );
      setTouched(allTouched);

      // Validate all fields
      const result = schema.safeParse(values);

      if (!result.success) {
        setErrors(formatZodError(result.error));
        return;
      }

      setIsSubmitting(true);
      try {
        await onSubmit(result.data);
      } finally {
        setIsSubmitting(false);
      }
    },
    [schema, values, onSubmit]
  );

  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  return {
    values,
    errors,
    touched,
    isSubmitting,
    isValid: Object.keys(errors).length === 0,
    handleChange,
    handleBlur,
    handleSubmit,
    validateAll,
    reset,
    setValues,
  };
}
```

### Form Component Example

Create `ui/components/forms/ProfileForm.tsx`:

```tsx
/**
 * PULSE Profile Form with Validation
 */

'use client';

import { useFormValidation } from '@/hooks/useFormValidation';
import { userProfileUpdateSchema, UserProfileUpdate } from '@/lib/validation/schemas/user';

export function ProfileForm({ initialData }: { initialData?: Partial<UserProfileUpdate> }) {
  const {
    values,
    errors,
    touched,
    isSubmitting,
    handleChange,
    handleBlur,
    handleSubmit,
  } = useFormValidation<UserProfileUpdate>({
    schema: userProfileUpdateSchema,
    initialValues: initialData,
    onSubmit: async (data) => {
      const response = await fetch('/api/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error('Failed to update profile');
      }
    },
  });

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="name" className="block text-sm font-medium">
          Name
        </label>
        <input
          type="text"
          id="name"
          value={values.name || ''}
          onChange={(e) => handleChange('name', e.target.value)}
          onBlur={() => handleBlur('name')}
          className={`mt-1 block w-full rounded-md border ${
            errors.name && touched.name ? 'border-red-500' : 'border-gray-300'
          } px-3 py-2`}
        />
        {errors.name && touched.name && (
          <p className="mt-1 text-sm text-red-600">{errors.name}</p>
        )}
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Email
        </label>
        <input
          type="email"
          id="email"
          value={values.email || ''}
          onChange={(e) => handleChange('email', e.target.value)}
          onBlur={() => handleBlur('email')}
          className={`mt-1 block w-full rounded-md border ${
            errors.email && touched.email ? 'border-red-500' : 'border-gray-300'
          } px-3 py-2`}
        />
        {errors.email && touched.email && (
          <p className="mt-1 text-sm text-red-600">{errors.email}</p>
        )}
      </div>

      <div>
        <label htmlFor="timezone" className="block text-sm font-medium">
          Timezone
        </label>
        <select
          id="timezone"
          value={values.timezone || ''}
          onChange={(e) => handleChange('timezone', e.target.value)}
          onBlur={() => handleBlur('timezone')}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
        >
          <option value="">Select timezone</option>
          <option value="America/New_York">Eastern Time</option>
          <option value="America/Chicago">Central Time</option>
          <option value="America/Denver">Mountain Time</option>
          <option value="America/Los_Angeles">Pacific Time</option>
        </select>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {isSubmitting ? 'Saving...' : 'Save Changes'}
      </button>
    </form>
  );
}
```

---

## File Upload Validation

### Create File Validation Utilities

Create `ui/lib/validation/file-validator.ts`:

```typescript
/**
 * PULSE File Upload Validator
 */

import { z } from 'zod';

// Allowed file types with MIME and extensions
export const ALLOWED_FILE_TYPES: Record<string, { mimes: string[]; exts: string[] }> = {
  image: {
    mimes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    exts: ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
  },
  document: {
    mimes: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
    ],
    exts: ['.pdf', '.doc', '.docx', '.txt'],
  },
  csv: {
    mimes: ['text/csv', 'application/csv'],
    exts: ['.csv'],
  },
};

// Maximum file sizes (in bytes)
export const MAX_FILE_SIZES: Record<string, number> = {
  image: 10 * 1024 * 1024,     // 10 MB
  document: 50 * 1024 * 1024,  // 50 MB
  csv: 100 * 1024 * 1024,      // 100 MB
  default: 10 * 1024 * 1024,   // 10 MB
};

// Dangerous file signatures (magic bytes)
const DANGEROUS_SIGNATURES = [
  [0x4d, 0x5a],                           // EXE, DLL
  [0x50, 0x4b, 0x03, 0x04],               // ZIP (could contain exe)
  [0x52, 0x61, 0x72, 0x21],               // RAR
  [0x7f, 0x45, 0x4c, 0x46],               // ELF (Linux executable)
  [0x23, 0x21],                           // Shell script (shebang)
];

export interface FileValidationOptions {
  allowedTypes: string[];
  maxSize?: number;
  checkSignature?: boolean;
}

export interface FileValidationResult {
  valid: boolean;
  error?: string;
  sanitizedName?: string;
}

/**
 * Validate file metadata
 */
export function validateFile(
  file: File,
  options: FileValidationOptions
): FileValidationResult {
  const { allowedTypes, maxSize, checkSignature = true } = options;

  // Check file size
  const maxFileSize = maxSize || MAX_FILE_SIZES.default;
  if (file.size > maxFileSize) {
    return {
      valid: false,
      error: `File too large. Maximum size is ${formatBytes(maxFileSize)}`,
    };
  }

  // Check file type
  const allowedMimes: string[] = [];
  const allowedExts: string[] = [];

  for (const type of allowedTypes) {
    if (ALLOWED_FILE_TYPES[type]) {
      allowedMimes.push(...ALLOWED_FILE_TYPES[type].mimes);
      allowedExts.push(...ALLOWED_FILE_TYPES[type].exts);
    }
  }

  // Check MIME type
  if (!allowedMimes.includes(file.type)) {
    return {
      valid: false,
      error: `File type not allowed. Allowed types: ${allowedExts.join(', ')}`,
    };
  }

  // Check extension
  const ext = getFileExtension(file.name);
  if (!allowedExts.includes(ext.toLowerCase())) {
    return {
      valid: false,
      error: `File extension not allowed. Allowed: ${allowedExts.join(', ')}`,
    };
  }

  // Sanitize filename
  const sanitizedName = sanitizeFilename(file.name);

  return {
    valid: true,
    sanitizedName,
  };
}

/**
 * Validate file content (magic bytes)
 */
export async function validateFileContent(
  file: File
): Promise<FileValidationResult> {
  const buffer = await file.slice(0, 8).arrayBuffer();
  const bytes = new Uint8Array(buffer);

  // Check for dangerous signatures
  for (const signature of DANGEROUS_SIGNATURES) {
    if (matchesSignature(bytes, signature)) {
      return {
        valid: false,
        error: 'File content does not match allowed types',
      };
    }
  }

  return { valid: true };
}

/**
 * Check if bytes match a signature
 */
function matchesSignature(bytes: Uint8Array, signature: number[]): boolean {
  if (bytes.length < signature.length) return false;

  for (let i = 0; i < signature.length; i++) {
    if (bytes[i] !== signature[i]) return false;
  }

  return true;
}

/**
 * Get file extension
 */
function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.');
  return lastDot >= 0 ? filename.slice(lastDot) : '';
}

/**
 * Sanitize filename
 */
export function sanitizeFilename(filename: string): string {
  // Remove path separators
  let safe = filename.replace(/[\/\\]/g, '_');

  // Remove null bytes
  safe = safe.replace(/\x00/g, '');

  // Remove leading dots (hidden files)
  safe = safe.replace(/^\.+/, '');

  // Replace dangerous characters
  safe = safe.replace(/[<>:"|?*]/g, '_');

  // Limit length
  if (safe.length > 255) {
    const ext = getFileExtension(safe);
    const name = safe.slice(0, 255 - ext.length);
    safe = name + ext;
  }

  // Ensure not empty
  if (!safe || safe === '.') {
    safe = 'unnamed_file';
  }

  return safe;
}

/**
 * Format bytes to human readable
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Zod schema for file validation
export const fileSchema = z.custom<File>((val) => val instanceof File, {
  message: 'Invalid file',
});

export const fileUploadSchema = z.object({
  file: fileSchema,
  category: z.enum(['image', 'document', 'csv']).optional(),
});
```

### File Upload Component

Create `ui/components/FileUpload.tsx`:

```tsx
/**
 * PULSE Secure File Upload Component
 */

'use client';

import { useState, useCallback } from 'react';
import {
  validateFile,
  validateFileContent,
  FileValidationResult,
} from '@/lib/validation/file-validator';

interface FileUploadProps {
  allowedTypes: string[];
  maxSize?: number;
  onUpload: (file: File, sanitizedName: string) => Promise<void>;
}

export function FileUpload({ allowedTypes, maxSize, onUpload }: FileUploadProps) {
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setError(null);
      setIsUploading(true);
      setProgress(10);

      try {
        // Validate file metadata
        const metaResult = validateFile(file, { allowedTypes, maxSize });
        if (!metaResult.valid) {
          setError(metaResult.error!);
          return;
        }

        setProgress(30);

        // Validate file content
        const contentResult = await validateFileContent(file);
        if (!contentResult.valid) {
          setError(contentResult.error!);
          return;
        }

        setProgress(50);

        // Upload file
        await onUpload(file, metaResult.sanitizedName!);
        setProgress(100);
      } catch (err) {
        setError('Upload failed. Please try again.');
      } finally {
        setIsUploading(false);
        // Reset input
        e.target.value = '';
      }
    },
    [allowedTypes, maxSize, onUpload]
  );

  return (
    <div className="w-full">
      <label className="block">
        <span className="sr-only">Choose file</span>
        <input
          type="file"
          onChange={handleFileSelect}
          disabled={isUploading}
          className="block w-full text-sm text-gray-500
            file:mr-4 file:py-2 file:px-4
            file:rounded-md file:border-0
            file:text-sm file:font-semibold
            file:bg-blue-50 file:text-blue-700
            hover:file:bg-blue-100
            disabled:opacity-50"
        />
      </label>

      {isUploading && (
        <div className="mt-2">
          <div className="bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
```

---

## Output Encoding

### Create Output Encoding Utilities

Create `ui/lib/validation/output-encoder.ts`:

```typescript
/**
 * PULSE Output Encoding
 * Context-aware output encoding to prevent XSS
 */

/**
 * Encode for HTML content
 */
export function encodeHtml(input: string): string {
  const entities: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
  };

  return input.replace(/[&<>"']/g, char => entities[char]);
}

/**
 * Encode for HTML attributes
 */
export function encodeAttribute(input: string): string {
  return input.replace(/[&<>"'\s]/g, char => {
    return `&#x${char.charCodeAt(0).toString(16)};`;
  });
}

/**
 * Encode for JavaScript string
 */
export function encodeJavaScript(input: string): string {
  return input
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t')
    .replace(/</g, '\\x3c')
    .replace(/>/g, '\\x3e');
}

/**
 * Encode for URL parameter
 */
export function encodeUrl(input: string): string {
  return encodeURIComponent(input);
}

/**
 * Encode for CSS value
 */
export function encodeCss(input: string): string {
  return input.replace(/[^a-zA-Z0-9-_]/g, char => {
    return `\\${char.charCodeAt(0).toString(16)} `;
  });
}

/**
 * Safe JSON stringify (prevents prototype pollution)
 */
export function safeJsonStringify(data: any): string {
  return JSON.stringify(data, (key, value) => {
    // Prevent __proto__ and constructor pollution
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      return undefined;
    }
    return value;
  });
}

/**
 * Create safe HTML content component
 */
export function createSafeHtml(html: string): { __html: string } {
  // Use DOMPurify in browser environment
  if (typeof window !== 'undefined') {
    // Note: In production, use DOMPurify library
    // import DOMPurify from 'dompurify';
    // return { __html: DOMPurify.sanitize(html) };
  }

  // Basic server-side sanitization
  return { __html: encodeHtml(html) };
}
```

---

## Database Input Sanitization

### Create Database Utilities

Create `ui/lib/validation/db-sanitizer.ts`:

```typescript
/**
 * PULSE Database Input Sanitizer
 * Prevent SQL injection and ensure safe database operations
 */

import { z } from 'zod';

// Safe identifier pattern (table names, column names)
const SAFE_IDENTIFIER = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

/**
 * Validate identifier (table/column name)
 */
export function validateIdentifier(identifier: string): boolean {
  return SAFE_IDENTIFIER.test(identifier);
}

/**
 * Escape identifier for dynamic SQL (use with caution)
 */
export function escapeIdentifier(identifier: string): string {
  if (!validateIdentifier(identifier)) {
    throw new Error(`Invalid identifier: ${identifier}`);
  }
  return `"${identifier}"`;
}

/**
 * Safe column list for SELECT
 */
export function safeColumnList(columns: string[]): string {
  return columns
    .filter(validateIdentifier)
    .map(escapeIdentifier)
    .join(', ');
}

/**
 * Safe order by clause
 */
export function safeOrderBy(
  column: string,
  direction: 'ASC' | 'DESC' = 'ASC'
): string {
  if (!validateIdentifier(column)) {
    throw new Error(`Invalid column for ORDER BY: ${column}`);
  }
  return `${escapeIdentifier(column)} ${direction}`;
}

/**
 * Pagination validation schema
 */
export const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

/**
 * Safe pagination helper
 */
export function safePagination(input: {
  page?: number | string;
  limit?: number | string;
}): { offset: number; limit: number } {
  const result = paginationSchema.parse(input);

  return {
    offset: (result.page - 1) * result.limit,
    limit: result.limit,
  };
}

/**
 * Safe search term (for LIKE queries)
 */
export function safeSearchTerm(term: string): string {
  // Escape LIKE special characters
  return term
    .replace(/\\/g, '\\\\')
    .replace(/%/g, '\\%')
    .replace(/_/g, '\\_');
}

/**
 * Build safe WHERE conditions
 */
export interface WhereCondition {
  column: string;
  operator: '=' | '!=' | '>' | '>=' | '<' | '<=' | 'LIKE' | 'IN' | 'IS NULL' | 'IS NOT NULL';
  value?: any;
}

export function buildWhereClause(
  conditions: WhereCondition[]
): { sql: string; params: any[] } {
  const parts: string[] = [];
  const params: any[] = [];
  let paramIndex = 1;

  for (const condition of conditions) {
    if (!validateIdentifier(condition.column)) {
      throw new Error(`Invalid column: ${condition.column}`);
    }

    const col = escapeIdentifier(condition.column);

    switch (condition.operator) {
      case 'IS NULL':
        parts.push(`${col} IS NULL`);
        break;
      case 'IS NOT NULL':
        parts.push(`${col} IS NOT NULL`);
        break;
      case 'IN':
        if (!Array.isArray(condition.value)) {
          throw new Error('IN operator requires array value');
        }
        const placeholders = condition.value.map(() => `$${paramIndex++}`).join(', ');
        parts.push(`${col} IN (${placeholders})`);
        params.push(...condition.value);
        break;
      case 'LIKE':
        parts.push(`${col} LIKE $${paramIndex++}`);
        params.push(`%${safeSearchTerm(condition.value)}%`);
        break;
      default:
        parts.push(`${col} ${condition.operator} $${paramIndex++}`);
        params.push(condition.value);
    }
  }

  return {
    sql: parts.length > 0 ? `WHERE ${parts.join(' AND ')}` : '',
    params,
  };
}
```

---

## Common Attack Prevention

### Create Security Validation Module

Create `ui/lib/validation/security-checks.ts`:

```typescript
/**
 * PULSE Security Validation Checks
 * Detect and prevent common attacks
 */

import { z } from 'zod';

/**
 * Detect potential SQL injection
 */
export function detectSqlInjection(input: string): boolean {
  const patterns = [
    /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)/i,
    /--/,
    /;.*(\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b)/i,
    /'\s*(OR|AND)\s*'?.*'?=/i,
    /'\s*(OR|AND)\s+\d+\s*=\s*\d+/i,
  ];

  return patterns.some(pattern => pattern.test(input));
}

/**
 * Detect potential XSS
 */
export function detectXss(input: string): boolean {
  const patterns = [
    /<script\b[^>]*>/i,
    /javascript:/i,
    /on\w+\s*=/i,  // onclick=, onerror=, etc.
    /<iframe\b/i,
    /<object\b/i,
    /<embed\b/i,
    /data:/i,
    /vbscript:/i,
  ];

  return patterns.some(pattern => pattern.test(input));
}

/**
 * Detect path traversal
 */
export function detectPathTraversal(input: string): boolean {
  const patterns = [
    /\.\./,
    /%2e%2e/i,
    /%252e%252e/i,
    /\.\.%c0%af/i,
    /\.\.%c1%9c/i,
  ];

  return patterns.some(pattern => pattern.test(input));
}

/**
 * Detect command injection
 */
export function detectCommandInjection(input: string): boolean {
  const patterns = [
    /[;&|`$]/,
    /\$\(/,
    /`.*`/,
    /\|\|/,
    /&&/,
  ];

  return patterns.some(pattern => pattern.test(input));
}

/**
 * Detect LDAP injection
 */
export function detectLdapInjection(input: string): boolean {
  const patterns = [
    /[()\\*]/,
    /\x00/,
  ];

  return patterns.some(pattern => pattern.test(input));
}

/**
 * Comprehensive security check
 */
export function securityCheck(
  input: string
): { safe: boolean; threats: string[] } {
  const threats: string[] = [];

  if (detectSqlInjection(input)) {
    threats.push('Potential SQL injection');
  }

  if (detectXss(input)) {
    threats.push('Potential XSS');
  }

  if (detectPathTraversal(input)) {
    threats.push('Potential path traversal');
  }

  if (detectCommandInjection(input)) {
    threats.push('Potential command injection');
  }

  if (detectLdapInjection(input)) {
    threats.push('Potential LDAP injection');
  }

  return {
    safe: threats.length === 0,
    threats,
  };
}

/**
 * Zod refinement for security checks
 */
export const secureString = z.string().refine(
  (value) => {
    const { safe } = securityCheck(value);
    return safe;
  },
  { message: 'Input contains potentially dangerous content' }
);

/**
 * Create secure schema wrapper
 */
export function withSecurityCheck<T extends z.ZodTypeAny>(
  schema: T
): z.ZodEffects<T> {
  return schema.refine(
    (value) => {
      if (typeof value === 'string') {
        const { safe } = securityCheck(value);
        return safe;
      }
      if (typeof value === 'object' && value !== null) {
        return Object.values(value).every((v) => {
          if (typeof v === 'string') {
            const { safe } = securityCheck(v);
            return safe;
          }
          return true;
        });
      }
      return true;
    },
    { message: 'Input contains potentially dangerous content' }
  );
}
```

---

## Testing and Validation

### Input Validation Test Suite

Create `ui/__tests__/validation.test.ts`:

```typescript
import { z } from 'zod';
import {
  schemas,
  sanitize,
  validateData,
  patterns,
} from '../lib/validation';
import {
  detectSqlInjection,
  detectXss,
  detectPathTraversal,
  detectCommandInjection,
  securityCheck,
} from '../lib/validation/security-checks';
import {
  validateFile,
  sanitizeFilename,
} from '../lib/validation/file-validator';

describe('Validation Utilities', () => {
  describe('schemas', () => {
    it('should validate email', () => {
      expect(schemas.email.safeParse('test@example.com').success).toBe(true);
      expect(schemas.email.safeParse('invalid').success).toBe(false);
      expect(schemas.email.safeParse('test@').success).toBe(false);
    });

    it('should validate UUID', () => {
      expect(schemas.uuid.safeParse('550e8400-e29b-41d4-a716-446655440000').success).toBe(true);
      expect(schemas.uuid.safeParse('not-a-uuid').success).toBe(false);
    });

    it('should enforce string length limits', () => {
      const schema = schemas.nonEmptyString(10);
      expect(schema.safeParse('hello').success).toBe(true);
      expect(schema.safeParse('').success).toBe(false);
      expect(schema.safeParse('a'.repeat(11)).success).toBe(false);
    });
  });

  describe('sanitize', () => {
    it('should strip HTML tags', () => {
      expect(sanitize.stripHtml('<script>alert(1)</script>')).toBe('alert(1)');
      expect(sanitize.stripHtml('<p>Hello</p>')).toBe('Hello');
    });

    it('should escape HTML entities', () => {
      expect(sanitize.escapeHtml('<script>')).toBe('&lt;script&gt;');
      expect(sanitize.escapeHtml('"test"')).toBe('&quot;test&quot;');
    });

    it('should remove control characters', () => {
      expect(sanitize.removeControlChars('hello\x00world')).toBe('helloworld');
      expect(sanitize.removeControlChars('test\x1fvalue')).toBe('testvalue');
    });

    it('should normalize unicode', () => {
      // This tests NFC normalization
      expect(sanitize.normalizeUnicode('café')).toBe('café');
    });
  });
});

describe('Security Checks', () => {
  describe('detectSqlInjection', () => {
    it('should detect SQL injection patterns', () => {
      expect(detectSqlInjection("1' OR '1'='1")).toBe(true);
      expect(detectSqlInjection('1; DROP TABLE users--')).toBe(true);
      expect(detectSqlInjection('UNION SELECT * FROM users')).toBe(true);
      expect(detectSqlInjection('normal input')).toBe(false);
    });
  });

  describe('detectXss', () => {
    it('should detect XSS patterns', () => {
      expect(detectXss('<script>alert(1)</script>')).toBe(true);
      expect(detectXss('javascript:alert(1)')).toBe(true);
      expect(detectXss('<img onerror=alert(1)>')).toBe(true);
      expect(detectXss('normal text')).toBe(false);
    });
  });

  describe('detectPathTraversal', () => {
    it('should detect path traversal patterns', () => {
      expect(detectPathTraversal('../../../etc/passwd')).toBe(true);
      expect(detectPathTraversal('%2e%2e%2f')).toBe(true);
      expect(detectPathTraversal('normal/path')).toBe(false);
    });
  });

  describe('detectCommandInjection', () => {
    it('should detect command injection patterns', () => {
      expect(detectCommandInjection('; ls -la')).toBe(true);
      expect(detectCommandInjection('| cat /etc/passwd')).toBe(true);
      expect(detectCommandInjection('$(whoami)')).toBe(true);
      expect(detectCommandInjection('normal input')).toBe(false);
    });
  });

  describe('securityCheck', () => {
    it('should identify multiple threats', () => {
      const result = securityCheck("<script>'; DROP TABLE--");
      expect(result.safe).toBe(false);
      expect(result.threats).toContain('Potential XSS');
      expect(result.threats).toContain('Potential SQL injection');
    });

    it('should pass safe input', () => {
      const result = securityCheck('Hello, this is a normal message.');
      expect(result.safe).toBe(true);
      expect(result.threats).toHaveLength(0);
    });
  });
});

describe('File Validation', () => {
  describe('sanitizeFilename', () => {
    it('should remove path separators', () => {
      expect(sanitizeFilename('../../../etc/passwd')).toBe('______etc_passwd');
      expect(sanitizeFilename('folder\\file.txt')).toBe('folder_file.txt');
    });

    it('should remove leading dots', () => {
      expect(sanitizeFilename('.hidden')).toBe('hidden');
      expect(sanitizeFilename('..hidden')).toBe('hidden');
    });

    it('should replace dangerous characters', () => {
      expect(sanitizeFilename('file<>:"|?*.txt')).toBe('file_______.txt');
    });

    it('should handle empty filenames', () => {
      expect(sanitizeFilename('')).toBe('unnamed_file');
      expect(sanitizeFilename('.')).toBe('unnamed_file');
    });
  });
});
```

### Integration Test Script

Create `scripts/test-input-validation.sh`:

```bash
#!/bin/bash
# PULSE Input Validation Integration Tests

set -e

API_URL="${1:-http://localhost:3000}"
echo "Testing input validation at: $API_URL"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

test_validation() {
    local name="$1"
    local endpoint="$2"
    local payload="$3"
    local expect_status="$4"

    echo -n "Testing: $name... "

    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL$endpoint" \
        -H "Content-Type: application/json" \
        -d "$payload")

    if [ "$status" == "$expect_status" ]; then
        echo -e "${GREEN}PASS${NC} (got $status)"
    else
        echo -e "${RED}FAIL${NC} (expected $expect_status, got $status)"
    fi
}

echo "=== Valid Input Tests ==="
test_validation "Valid chat message" "/api/chat" \
    '{"message": "Hello, how are you?"}' "200"

test_validation "Valid email format" "/api/profile" \
    '{"email": "test@example.com"}' "200"

echo ""
echo "=== Invalid Input Tests ==="
test_validation "Empty message" "/api/chat" \
    '{"message": ""}' "400"

test_validation "Message too long" "/api/chat" \
    "{\"message\": \"$(printf 'a%.0s' {1..10000})\"}" "400"

test_validation "Invalid email" "/api/profile" \
    '{"email": "not-an-email"}' "400"

echo ""
echo "=== Security Tests ==="
test_validation "SQL injection in message" "/api/chat" \
    '{"message": "1'\'' OR '\''1'\''='\''1"}' "400"

test_validation "XSS in message" "/api/chat" \
    '{"message": "<script>alert(1)</script>"}' "400"

echo ""
echo "=== Input Validation Tests Complete ==="
```

---

## Migration Checklist

### Phase 1: Setup

- [ ] Install Zod: `npm install zod`
- [ ] Create validation utilities in `ui/lib/validation/`
- [ ] Create common schemas for reuse
- [ ] Set up validation error formatting

### Phase 2: API Validation

- [ ] Create API validation middleware
- [ ] Define schemas for each API endpoint
- [ ] Apply validation to all POST/PUT/PATCH routes
- [ ] Add request logging for validation failures

### Phase 3: Form Validation

- [ ] Create form validation hook
- [ ] Update all forms to use validation
- [ ] Add client-side validation feedback
- [ ] Ensure server-side validation matches

### Phase 4: File Uploads

- [ ] Create file validation utilities
- [ ] Implement content type validation
- [ ] Add file signature checking
- [ ] Create secure upload component

### Phase 5: Security Checks

- [ ] Create security check utilities
- [ ] Add injection detection
- [ ] Implement output encoding
- [ ] Add database sanitization

### Phase 6: Testing

- [ ] Write unit tests for validators
- [ ] Create integration tests
- [ ] Run security testing
- [ ] Document edge cases

---

## Best Practices Summary

1. **Validate Everything**: Never trust user input
2. **Allowlist Over Denylist**: Define what's allowed, reject everything else
3. **Type Safety**: Use Zod for type-safe validation
4. **Context-Aware Encoding**: Encode output for the target context
5. **Defense in Depth**: Validate at multiple layers
6. **Fail Securely**: Reject invalid input with clear errors
7. **Log Failures**: Track validation failures for security monitoring

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [promptsecurity.md](promptsecurity.md) - Prompt injection protection
- [wafconfig.md](wafconfig.md) - Web Application Firewall
- [ratelimiting.md](ratelimiting.md) - Rate limiting implementation
