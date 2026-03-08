# Publishing ContextForge to the VS Code Marketplace

This guide covers publishing the ContextForge VS Code extension to the Marketplace, setting up CI/CD for releases, and monetisation strategies.

---

## Part 1: Publishing to the VS Code Marketplace

### Prerequisites

1. **A Microsoft account** -- sign up at https://account.microsoft.com
2. **An Azure DevOps organisation** -- create one at https://dev.azure.com (free)
3. **A Personal Access Token (PAT)** from Azure DevOps with **Marketplace (Manage)** scope
4. **Node.js 18+** and **npm**

### Step 1 -- Create a Publisher

1. Go to https://marketplace.visualstudio.com/manage
2. Sign in with your Microsoft account.
3. Click **Create publisher**.
4. Choose an ID (e.g., `contextforge`) and a display name (e.g., `ContextForge`).
5. Update `package.json` so the `publisher` field matches:

```json
{
  "publisher": "contextforge"
}
```

### Step 2 -- Generate a Personal Access Token

1. Go to https://dev.azure.com → your organisation → **User settings** (top right) → **Personal access tokens**.
2. Click **New Token**.
3. Set:
   - Name: `vsce-publish`
   - Organisation: **All accessible organisations**
   - Expiration: 1 year
   - Scopes: **Custom defined** → check **Marketplace > Manage**
4. Click **Create** and copy the token immediately. You will not see it again.

### Step 3 -- Install vsce

```bash
npm install -g @vscode/vsce
```

### Step 4 -- Prepare the Extension

Before publishing, make sure the extension is ready:

```bash
cd vscode-extension

# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Run tests (if available)
npm test
```

#### Update `package.json` for Marketplace

Ensure these fields are set:

```json
{
  "name": "contextforge",
  "displayName": "ContextForge - AI Coding Assistant",
  "description": "Local-first AI coding assistant with inline completion, multi-file editing, semantic search, and 20+ integrated features.",
  "version": "1.0.0",
  "publisher": "contextforge",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/contextforge/contextforge"
  },
  "icon": "media/icon.png",
  "galleryBanner": {
    "color": "#1e1e2e",
    "theme": "dark"
  },
  "categories": [
    "Programming Languages",
    "Machine Learning",
    "Snippets",
    "Other"
  ],
  "keywords": [
    "ai",
    "code-completion",
    "copilot",
    "assistant",
    "semantic-search",
    "code-review",
    "refactoring",
    "context-engine"
  ],
  "engines": {
    "vscode": "^1.74.0"
  }
}
```

#### Create an Icon

Place a 128x128 or 256x256 PNG at `vscode-extension/media/icon.png`.

#### Create a CHANGELOG

Create `vscode-extension/CHANGELOG.md`:

```markdown
# Change Log

## 1.0.0 (Initial Release)
- Inline code completion (Tab)
- Inline editing (Ctrl+K)
- Multi-file agent mode
- AI chat with @ mentions
- Smart apply
- Composer (long-running agent)
- Privacy mode toggle
- Diff preview for all AI edits
- Project rules support
- Documentation indexing
- Symbol navigation
- Multi-cursor AI editing
- Auto linting after edits
- Undo/redo AI changes
- Conversation branching
- Background indexing on save
- Git diff context
- Web search integration
- Image input in chat
```

### Step 5 -- Login and Publish

```bash
# Login with your PAT
vsce login contextforge
# Paste your Personal Access Token when prompted

# Package (creates .vsix file)
vsce package

# Publish
vsce publish
```

The extension will appear at `https://marketplace.visualstudio.com/items?itemName=contextforge.contextforge` within a few minutes.

### Step 6 -- Verify

1. Go to https://marketplace.visualstudio.com and search for "ContextForge".
2. Install it from VS Code: **Extensions** sidebar → search "ContextForge" → **Install**.

---

## Part 2: Automated Publishing with GitHub Actions

Create `.github/workflows/publish-extension.yml`:

```yaml
name: Publish VS Code Extension

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 18

      - name: Install dependencies
        working-directory: vscode-extension
        run: npm ci

      - name: Compile
        working-directory: vscode-extension
        run: npm run compile

      - name: Publish to Marketplace
        working-directory: vscode-extension
        run: npx @vscode/vsce publish -p ${{ secrets.VSCE_PAT }}

      - name: Publish to Open VSX (optional)
        working-directory: vscode-extension
        run: npx ovsx publish -p ${{ secrets.OVSX_PAT }}
        continue-on-error: true
```

Add your PAT as a GitHub secret named `VSCE_PAT`.

To release:

```bash
# Update version in package.json
cd vscode-extension
npm version patch    # or minor, major

# Tag and push
git add .
git commit -m "release: v1.0.1"
git tag v1.0.1
git push && git push --tags
```

---

## Part 3: Open VSX Registry (for non-Microsoft editors)

Open VSX is the open marketplace used by VS Codium, Gitpod, Eclipse Theia, and other VS Code-compatible editors.

1. Create an account at https://open-vsx.org
2. Generate a token at https://open-vsx.org/user-settings/tokens
3. Publish:

```bash
npm install -g ovsx
ovsx publish -p your-open-vsx-token
```

---

## Part 4: Monetisation Options

### Option 1: Open Source + Hosted Backend (SaaS)

**How it works**: The extension is free and open source. Revenue comes from a hosted backend service that provides managed LLM inference, vector indexing, and storage.

| Tier | Price | Includes |
|------|-------|----------|
| Free | $0/mo | Local LLMs only, self-hosted backend |
| Pro | $10-20/mo | Managed cloud backend, fast models, 100k indexed files |
| Team | $20-40/user/mo | Shared team indexes, admin dashboard, SSO |
| Enterprise | Custom | On-premise deployment, SLA, priority support |

**Implementation**:
- Extension connects to `contextforge.apiUrl` -- either self-hosted or your cloud service.
- Add a `contextforge.cloudApiKey` setting and check it in the extension.
- The backend validates API keys and enforces tier limits.

**Pros**: Low friction adoption, large open-source community, recurring revenue.
**Cons**: Must run and maintain cloud infrastructure.

### Option 2: Freemium Extension

**How it works**: The extension is free with core features. Premium features require a license key.

| Feature | Free | Pro ($10-15/mo) |
|---------|------|-----------------|
| AI Chat | 50 msgs/day | Unlimited |
| Inline Completion | 100/day | Unlimited |
| Agent Mode | 5/day | Unlimited |
| Composer | No | Yes |
| Documentation Indexing | 1 source | Unlimited |
| Priority Models | No | Yes (GPT-4, Claude) |
| Privacy Mode | Yes | Yes |

**Implementation**:
- Use a license server (Gumroad, LemonSqueezy, Stripe) to validate keys.
- Store the key in VS Code's `SecretStorage`.
- Check limits client-side and server-side.

**Pros**: Simple to implement, no infrastructure to manage.
**Cons**: Can be bypassed since the extension is client-side.

### Option 3: Marketplace Paid Extension

**How it works**: Publish as a paid extension on the VS Code Marketplace.

> Note: As of 2026, the VS Code Marketplace does not natively support paid extensions. You would need to use a third-party licensing service (Gumroad, Paddle, LemonSqueezy) and check the license in your extension.

**Implementation pattern**:

```typescript
// In extension.ts activation
const licenseKey = await context.secrets.get('contextforge.license');
if (!licenseKey) {
  const key = await vscode.window.showInputBox({ prompt: 'Enter your ContextForge license key' });
  if (key && await validateLicense(key)) {
    await context.secrets.store('contextforge.license', key);
  }
}
```

### Option 4: Sponsorship / Donations

**Platforms**: GitHub Sponsors, Open Collective, Ko-fi, Buy Me a Coffee.

**How it works**: The project is fully open source. Revenue comes from voluntary sponsorships.

**Pros**: Maximum adoption, community goodwill.
**Cons**: Unpredictable revenue, usually insufficient as a sole income source.

### Option 5: Enterprise Licensing

**How it works**: The extension and core backend are open source. Enterprise features (SSO, audit logs, compliance, dedicated support) are behind a commercial license.

| Feature | Community | Enterprise |
|---------|-----------|------------|
| All 20 features | Yes | Yes |
| Self-hosted | Yes | Yes |
| SSO/SAML | No | Yes |
| Audit logging | No | Yes |
| Admin dashboard | No | Yes |
| SLA | No | 99.9% |
| Priority support | Community | Dedicated |
| Air-gapped deployment | No | Yes |

**Pros**: High revenue per customer, no impact on open-source adoption.
**Cons**: Longer sales cycles, requires sales effort.

### Option 6: Hybrid (Recommended)

Combine multiple approaches:

1. **Core extension**: Free and open source (MIT license).
2. **Hosted backend (SaaS)**: Paid tiers for managed infrastructure.
3. **Enterprise license**: Premium features for organisations.
4. **GitHub Sponsors**: For individual supporters.

This is the model used by most successful open-source developer tools (GitLens, Cody, Continue).

---

## Part 5: License Considerations

| License | Commercial Use | Monetisation Compatibility |
|---------|---------------|--------------------------|
| **MIT** | Yes | Works with all models. Most permissive. |
| **Apache 2.0** | Yes | Like MIT but includes patent grant. |
| **AGPL** | Restricted | Forces SaaS users to open-source their modifications. Good for forcing enterprise licenses. |
| **BSL** | Time-delayed | Free after X years, commercial license needed before. Used by MariaDB, CockroachDB. |
| **Elastic License 2.0** | Restricted | Prevents competitors from offering your product as a service. |

**Recommendation**: Use **MIT** for the extension and open-source backend. Monetise via hosted services and enterprise features.

---

## Part 6: Marketing Checklist

- [ ] Write a compelling Marketplace description with screenshots
- [ ] Create a demo video (2-3 minutes)
- [ ] Publish a blog post / Product Hunt launch
- [ ] Share on Hacker News, Reddit (/r/vscode, /r/programming), Twitter/X
- [ ] Add badges to README: Marketplace installs, rating, version
- [ ] Set up a landing page (e.g., contextforge.dev)
- [ ] Create a Discord or GitHub Discussions community
- [ ] Write comparison guides (ContextForge vs Cursor, vs GitHub Copilot)
- [ ] Submit to VS Code extension roundup lists and newsletters

---

## Quick Reference Commands

```bash
# Package the extension
cd vscode-extension && npx @vscode/vsce package

# Publish to Marketplace
npx @vscode/vsce publish -p YOUR_PAT

# Publish to Open VSX
npx ovsx publish -p YOUR_OVSX_TOKEN

# Bump version
npm version patch    # 1.0.0 -> 1.0.1
npm version minor    # 1.0.0 -> 1.1.0
npm version major    # 1.0.0 -> 2.0.0

# Unpublish (careful!)
npx @vscode/vsce unpublish contextforge.contextforge
```
