// test-github-token.mjs
import 'dotenv/config';

const token = process.env.GITHUB_TOKEN;
const org = process.env.GITHUB_ORG;

if (!token) {
  console.error('ERROR: GITHUB_TOKEN is missing in .env');
  process.exit(1);
}
if (!org) {
  console.error('ERROR: GITHUB_ORG is missing in .env');
  process.exit(1);
}

async function gh(path, options = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'User-Agent': 'github-token-tester',
      'Accept': 'application/vnd.github+json',
      ...(options.headers || {})
    }
  });

  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }

  return { res, body };
}

(async () => {
  console.log('--- Testing GitHub token ---');
  console.log(`Org: ${org}`);

  // 1) Basic auth + identity + scopes
  const { res: userRes, body: user } = await gh('/user');

  if (userRes.status === 401) {
    console.error('❌ Token is INVALID or has no access to /user (401 Unauthorized).');
    console.error(user);
    process.exit(1);
  }

  if (!userRes.ok) {
    console.error(`❌ Failed to call /user. Status: ${userRes.status}`);
    console.error(user);
    process.exit(1);
  }

  const scopes = userRes.headers.get('x-oauth-scopes') || '';
  const acceptedScopes = userRes.headers.get('x-accepted-oauth-scopes') || '';

  console.log('✅ Token is valid.');
  console.log(`User: ${user.login} (id: ${user.id})`);
  console.log(`Token scopes: ${scopes || '(none reported)'}`);
  console.log(`Accepted scopes for /user: ${acceptedScopes || '(none reported)'}`);
  console.log('');

  // 2) Org membership visibility
  const { res: orgsRes, body: orgs } = await gh('/user/orgs?per_page=100');

  if (!orgsRes.ok) {
    console.warn(`⚠️ Could not list /user/orgs (status ${orgsRes.status}).`);
  } else if (Array.isArray(orgs)) {
    const match = orgs.find(o => o.login?.toLowerCase() === org.toLowerCase());
    if (match) {
      console.log(`✅ Token can see membership in org "${org}".`);
      console.log(`Role: ${match.role || 'unknown/hidden'}`);
    } else {
      console.log(`⚠️ Token does NOT show membership in org "${org}" via /user/orgs.`);
      console.log('   This may mean: not a member, or membership is hidden, or limited scopes.');
    }
  }

  // 3) Basic access to org object
  const { res: orgRes, body: orgInfo } = await gh(`/orgs/${encodeURIComponent(org)}`);
  if (orgRes.ok) {
    console.log('');
    console.log(`✅ Token can access /orgs/${org}.`);
    console.log(`Org name: ${orgInfo.name || orgInfo.login}`);
    console.log(`Visibility: ${orgInfo.visibility || orgInfo.type}`);
  } else if (orgRes.status === 404) {
    console.log('');
    console.log(`❌ Org "${org}" not found (404). Check GITHUB_ORG value.`);
  } else if (orgRes.status === 403) {
    console.log('');
    console.log(`❌ Token forbidden from /orgs/${org} (403). Likely missing org-level permission or SSO enforcement.`);
  }

  console.log('\n--- Summary ---');
  console.log('- If scopes look too narrow, adjust them in GitHub PAT settings.');
  console.log('- Use the X-OAuth-Scopes output above to understand what this token can actually do.');
})();