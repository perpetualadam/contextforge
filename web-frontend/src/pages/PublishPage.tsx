import type { ReactNode } from 'react';
import { ExternalLink, Info } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../components/ui';

const PLAY_CONSOLE = 'https://play.google.com/console';
const APP_STORE_CONNECT = 'https://appstoreconnect.apple.com';
const ANDROID_PUBLISH_DOCS = 'https://developer.android.com/studio/publish';
const APPLE_SUBMIT_DOCS = 'https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases';

export function PublishPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto pb-16">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Publish &amp; app stores
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          Distribute the ContextForge extension and ship mobile apps you build in your editor. This hub mirrors workflows platforms like Base44 highlight—adapted for a local-first coding assistant.
        </p>
      </div>

      <Card className="mb-8 border-primary-200 dark:border-primary-800 bg-primary-50/50 dark:bg-primary-950/20">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-primary-600 dark:text-primary-400 shrink-0 mt-0.5" aria-hidden />
            <div className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
              <p>
                <strong className="text-gray-900 dark:text-gray-100">Base44</strong> is an app-builder platform with hosted builds and direct submission flows for Google Play and the App Store.
              </p>
              <p>
                <strong className="text-gray-900 dark:text-gray-100">ContextForge</strong> is a VS Code–centric AI assistant and context engine. It does not run cloud AAB/IPA builds; you produce release artifacts with Android Studio, Gradle, Xcode, Flutter, React Native, or your CI pipeline, then follow the checklists below to list apps in each store.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="space-y-8">
        <StoreSection
          title="VS Code Marketplace (extension)"
          description="Publish the ContextForge extension so others can install it from the Marketplace—your primary &quot;store&quot; for this project."
        >
          <ol className="list-decimal list-inside space-y-2 text-gray-600 dark:text-gray-400 text-sm">
            <li>Create a publisher at Microsoft Marketplace and a PAT with Marketplace (Manage) scope.</li>
            <li>From the repo: compile the extension, then package and publish with vsce.</li>
          </ol>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-3">
            Full steps are in the repository <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">PUBLISHING.md</code>.
          </p>
          <div className="mt-4">
            <CodeBlock
              language="bash"
              code={`cd vscode-extension
npm ci && npm run compile
npx @vscode/vsce package
npx @vscode/vsce publish -p YOUR_PAT`}
              maxHeight="12rem"
            />
          </div>
          <ExternalAnchor href="https://marketplace.visualstudio.com/manage">Manage publishers</ExternalAnchor>
        </StoreSection>

        <StoreSection
          title="Open VSX Registry"
          description="Alternative marketplace for VS Code–compatible editors (VSCodium, Gitpod, Theia)."
        >
          <CodeBlock
            language="bash"
            code={`cd vscode-extension
npx ovsx publish -p YOUR_OPEN_VSX_TOKEN`}
            maxHeight="8rem"
          />
          <ExternalAnchor href="https://open-vsx.org">Open VSX</ExternalAnchor>
        </StoreSection>

        <StoreSection
          title="Google Play (Android apps)"
          description="When your workspace is an Android, Flutter, or React Native project, use this flow to release to the Play Store—similar outcome to Base44’s Play publishing, using your own build pipeline."
        >
          <ol className="list-decimal list-inside space-y-2 text-gray-600 dark:text-gray-400 text-sm">
            <li>
              <strong className="text-gray-800 dark:text-gray-200">Developer account</strong> — one-time registration in{' '}
              <a className="text-primary-600 dark:text-primary-400 hover:underline" href={PLAY_CONSOLE} target="_blank" rel="noopener noreferrer">Google Play Console</a>.
            </li>
            <li>
              <strong className="text-gray-800 dark:text-gray-200">Signing</strong> — use Play App Signing; upload an AAB (Android App Bundle), not a raw APK, for new listings.
            </li>
            <li>
              <strong className="text-gray-800 dark:text-gray-200">Release build</strong> — generate a signed bundle from your project (examples below).
            </li>
            <li>
              <strong className="text-gray-800 dark:text-gray-200">Store listing</strong> — screenshots, privacy policy, content rating, and target API level per current Google policies.
            </li>
            <li>
              <strong className="text-gray-800 dark:text-gray-200">Review</strong> — submit for review; monitor Play Console for policy feedback.
            </li>
          </ol>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-4">Typical local commands (adjust module paths as needed):</p>
          <div className="mt-2 space-y-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Gradle (Kotlin/Java)</p>
            <CodeBlock language="bash" code="./gradlew bundleRelease" maxHeight="6rem" />
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Flutter</p>
            <CodeBlock language="bash" code="flutter build appbundle" maxHeight="6rem" />
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">React Native (new architecture)</p>
            <CodeBlock language="bash" code="cd android && ./gradlew bundleRelease" maxHeight="6rem" />
          </div>
          <div className="flex flex-wrap gap-4 mt-4">
            <ExternalAnchor href={PLAY_CONSOLE}>Play Console</ExternalAnchor>
            <ExternalAnchor href={ANDROID_PUBLISH_DOCS}>Android publishing overview</ExternalAnchor>
          </div>
        </StoreSection>

        <StoreSection
          title="Apple App Store (iOS / iPadOS)"
          description="Ship iOS builds with Xcode or your CI; upload to App Store Connect and submit for review."
        >
          <ol className="list-decimal list-inside space-y-2 text-gray-600 dark:text-gray-400 text-sm">
            <li>Enroll in the Apple Developer Program.</li>
            <li>Archive in Xcode (or use <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">xcodebuild</code> / fastlane in CI).</li>
            <li>Upload to App Store Connect, complete metadata and compliance, then submit for review.</li>
          </ol>
          <div className="flex flex-wrap gap-4 mt-4">
            <ExternalAnchor href={APP_STORE_CONNECT}>App Store Connect</ExternalAnchor>
            <ExternalAnchor href={APPLE_SUBMIT_DOCS}>Apple distribution docs</ExternalAnchor>
          </div>
        </StoreSection>

        <StoreSection
          title="Community templates (Base44-style)"
          description="Base44 offers shareable app and workspace templates. ContextForge does not host a template marketplace; you can version templates in Git and share them as repositories or gists."
        >
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Use project rules (<code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">.contextforge-rules</code>) and documentation indexing so teams reuse the same AI context across repos.
          </p>
        </StoreSection>
      </section>
    </div>
  );
}

function StoreSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex-col items-start gap-1">
        <CardTitle>{title}</CardTitle>
        <p className="text-sm text-gray-500 dark:text-gray-400 font-normal">{description}</p>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function ExternalAnchor({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 text-sm text-primary-600 dark:text-primary-400 hover:underline"
    >
      <ExternalLink className="w-4 h-4 shrink-0" />
      {children}
    </a>
  );
}
