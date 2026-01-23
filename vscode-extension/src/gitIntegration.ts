import * as vscode from 'vscode';
import * as path from 'path';
import simpleGit, { SimpleGit, StatusResult, BranchSummary } from 'simple-git';
import { Octokit } from '@octokit/rest';
import axios from 'axios';

/**
 * VCS Provider type - supports GitHub, GitLab, and Bitbucket
 */
export type VCSProvider = 'github' | 'gitlab' | 'bitbucket';

interface GitConfig {
    gitEnabled: boolean;
    githubToken: string;
    gitlabToken: string;
    gitlabUrl: string;
    bitbucketToken: string;
    bitbucketUsername: string;
    autoCommitMessages: boolean;
    defaultBranch: string;
    vcsProvider: VCSProvider;
}

interface CommitMessageRequest {
    diff: string;
    staged_files: string[];
    branch: string;
    recent_commits: string[];
}

interface CommitMessageResponse {
    message: string;
    description?: string;
    confidence: number;
}

/**
 * Repository information parsed from remote URL
 */
interface RepoInfo {
    owner: string;
    repo: string;
    provider: VCSProvider;
}

export class GitIntegration {
    private git: SimpleGit;
    private octokit: Octokit | null = null;
    private workspaceRoot: string;
    private config: GitConfig;
    private apiUrl: string;

    constructor(workspaceRoot: string, config: GitConfig, apiUrl: string) {
        this.workspaceRoot = workspaceRoot;
        this.config = config;
        this.apiUrl = apiUrl;
        this.git = simpleGit(workspaceRoot);

        // Initialize GitHub client if token provided
        if (config.githubToken) {
            this.octokit = new Octokit({
                auth: config.githubToken
            });
        }
    }

    /**
     * Get the current VCS provider based on configuration or auto-detect from remote URL
     */
    async getVCSProvider(): Promise<VCSProvider> {
        if (this.config.vcsProvider && this.config.vcsProvider !== 'github') {
            return this.config.vcsProvider;
        }

        // Auto-detect from remote URL
        const remoteUrl = await this.getRemoteUrl();
        if (remoteUrl) {
            if (remoteUrl.includes('gitlab.com') || remoteUrl.includes('gitlab')) {
                return 'gitlab';
            }
            if (remoteUrl.includes('bitbucket.org') || remoteUrl.includes('bitbucket')) {
                return 'bitbucket';
            }
        }

        return 'github';
    }

    /**
     * Get the appropriate API token for the current VCS provider
     */
    private getProviderToken(provider: VCSProvider): string {
        switch (provider) {
            case 'gitlab':
                return this.config.gitlabToken || '';
            case 'bitbucket':
                return this.config.bitbucketToken || '';
            case 'github':
            default:
                return this.config.githubToken || '';
        }
    }

    async isGitRepository(): Promise<boolean> {
        try {
            await this.git.status();
            return true;
        } catch (error) {
            return false;
        }
    }

    async getStatus(): Promise<StatusResult> {
        return await this.git.status();
    }

    async getBranches(): Promise<BranchSummary> {
        return await this.git.branch();
    }

    async getCurrentBranch(): Promise<string> {
        const branches = await this.getBranches();
        return branches.current;
    }

    async createBranch(branchName: string, checkout: boolean = true): Promise<void> {
        if (checkout) {
            await this.git.checkoutLocalBranch(branchName);
        } else {
            await this.git.branch([branchName]);
        }
    }

    async switchBranch(branchName: string): Promise<void> {
        await this.git.checkout(branchName);
    }

    async deleteBranch(branchName: string, force: boolean = false): Promise<void> {
        const flags = force ? ['-D'] : ['-d'];
        await this.git.branch([...flags, branchName]);
    }

    async pull(remote: string = 'origin', branch?: string): Promise<void> {
        if (branch) {
            await this.git.pull(remote, branch);
        } else {
            await this.git.pull();
        }
    }

    async push(remote: string = 'origin', branch?: string, setUpstream: boolean = false): Promise<void> {
        const currentBranch = branch || await this.getCurrentBranch();
        
        if (setUpstream) {
            await this.git.push(['-u', remote, currentBranch]);
        } else {
            await this.git.push(remote, currentBranch);
        }
    }

    async generateCommitMessage(stagedFiles?: string[]): Promise<string> {
        if (!this.config.autoCommitMessages) {
            return '';
        }

        try {
            // Get diff of staged changes
            const diff = await this.git.diff(['--cached']);
            
            if (!diff.trim()) {
                throw new Error('No staged changes found');
            }

            // Get list of staged files if not provided
            if (!stagedFiles) {
                const status = await this.getStatus();
                stagedFiles = [...status.staged, ...status.modified, ...status.created];
            }

            // Get recent commits for context
            const log = await this.git.log({ maxCount: 5 });
            const recentCommits = log.all.map((commit: any) => commit.message);

            // Get current branch
            const branch = await this.getCurrentBranch();

            const request: CommitMessageRequest = {
                diff: diff,
                staged_files: stagedFiles,
                branch: branch,
                recent_commits: recentCommits
            };

            // Call API Gateway to generate commit message
            const response = await axios.post(`${this.apiUrl}/git/commit-message`, request, {
                timeout: 30000
            });

            const result: CommitMessageResponse = response.data;
            
            if (result.confidence < 0.7) {
                vscode.window.showWarningMessage(
                    `AI commit message has low confidence (${Math.round(result.confidence * 100)}%). Please review carefully.`
                );
            }

            return result.description ? 
                `${result.message}\n\n${result.description}` : 
                result.message;

        } catch (error) {
            console.error('Failed to generate commit message:', error);
            vscode.window.showErrorMessage(`Failed to generate commit message: ${error}`);
            return '';
        }
    }

    async commit(message?: string, addAll: boolean = false): Promise<void> {
        try {
            // Add all files if requested
            if (addAll) {
                await this.git.add('.');
            }

            // Generate commit message if not provided
            if (!message && this.config.autoCommitMessages) {
                message = await this.generateCommitMessage();
            }

            // Fallback to user input if no message
            if (!message) {
                message = await vscode.window.showInputBox({
                    prompt: 'Enter commit message',
                    placeHolder: 'feat: add new feature'
                });
            }

            if (!message) {
                throw new Error('Commit message is required');
            }

            await this.git.commit(message);
            vscode.window.showInformationMessage(`Committed: ${message.split('\n')[0]}`);

        } catch (error) {
            console.error('Commit failed:', error);
            vscode.window.showErrorMessage(`Commit failed: ${error}`);
            throw error;
        }
    }

    async getRemoteUrl(): Promise<string | null> {
        try {
            const remotes = await this.git.getRemotes(true);
            const origin = remotes.find((remote: any) => remote.name === 'origin');
            return origin?.refs?.push || null;
        } catch (error) {
            return null;
        }
    }

    /**
     * Parse repository URL for any supported VCS provider (GitHub, GitLab, Bitbucket)
     */
    async parseRepoUrl(url: string): Promise<RepoInfo | null> {
        // GitHub patterns
        const githubPatterns = [
            /github\.com[\/:]([^\/]+)\/([^\/\.]+)/,
            /github\.com\/([^\/]+)\/([^\/]+)\.git/
        ];

        // GitLab patterns (both gitlab.com and self-hosted)
        const gitlabPatterns = [
            /gitlab\.com[\/:]([^\/]+)\/([^\/\.]+)/,
            /gitlab\.com\/([^\/]+)\/([^\/]+)\.git/,
            /gitlab[^\/]*[\/:]([^\/]+)\/([^\/\.]+)/  // Self-hosted GitLab
        ];

        // Bitbucket patterns
        const bitbucketPatterns = [
            /bitbucket\.org[\/:]([^\/]+)\/([^\/\.]+)/,
            /bitbucket\.org\/([^\/]+)\/([^\/]+)\.git/
        ];

        // Check GitHub
        for (const pattern of githubPatterns) {
            const match = url.match(pattern);
            if (match && url.includes('github')) {
                return { owner: match[1], repo: match[2].replace('.git', ''), provider: 'github' };
            }
        }

        // Check GitLab
        for (const pattern of gitlabPatterns) {
            const match = url.match(pattern);
            if (match && (url.includes('gitlab') || this.config.vcsProvider === 'gitlab')) {
                return { owner: match[1], repo: match[2].replace('.git', ''), provider: 'gitlab' };
            }
        }

        // Check Bitbucket
        for (const pattern of bitbucketPatterns) {
            const match = url.match(pattern);
            if (match && url.includes('bitbucket')) {
                return { owner: match[1], repo: match[2].replace('.git', ''), provider: 'bitbucket' };
            }
        }

        return null;
    }

    /**
     * @deprecated Use parseRepoUrl instead
     */
    async parseGitHubUrl(url: string): Promise<{ owner: string; repo: string } | null> {
        const result = await this.parseRepoUrl(url);
        if (result) {
            return { owner: result.owner, repo: result.repo };
        }
        return null;
    }

    /**
     * Create a pull/merge request for the current branch
     * Supports GitHub, GitLab, and Bitbucket
     */
    async createPullRequest(title: string, body: string, base: string = 'main'): Promise<void> {
        const remoteUrl = await this.getRemoteUrl();
        if (!remoteUrl) {
            throw new Error('No remote repository found');
        }

        const repoInfo = await this.parseRepoUrl(remoteUrl);
        if (!repoInfo) {
            throw new Error('Could not parse repository information');
        }

        const currentBranch = await this.getCurrentBranch();
        const provider = repoInfo.provider;
        const token = this.getProviderToken(provider);

        if (!token) {
            throw new Error(`${provider} token not configured`);
        }

        try {
            switch (provider) {
                case 'github':
                    await this.createGitHubPR(repoInfo, title, body, currentBranch, base);
                    break;
                case 'gitlab':
                    await this.createGitLabMR(repoInfo, title, body, currentBranch, base);
                    break;
                case 'bitbucket':
                    await this.createBitbucketPR(repoInfo, title, body, currentBranch, base);
                    break;
            }
        } catch (error: any) {
            console.error(`Failed to create pull request on ${provider}:`, error);
            vscode.window.showErrorMessage(`Failed to create pull request: ${error.message}`);
            throw error;
        }
    }

    /**
     * Create a GitHub Pull Request
     */
    private async createGitHubPR(
        repoInfo: RepoInfo,
        title: string,
        body: string,
        head: string,
        base: string
    ): Promise<void> {
        if (!this.octokit) {
            throw new Error('GitHub token not configured');
        }

        const response = await this.octokit.pulls.create({
            owner: repoInfo.owner,
            repo: repoInfo.repo,
            title: title,
            body: body,
            head: head,
            base: base
        });

        vscode.window.showInformationMessage(
            `Pull request created: ${response.data.html_url}`,
            'Open PR'
        ).then(selection => {
            if (selection === 'Open PR') {
                vscode.env.openExternal(vscode.Uri.parse(response.data.html_url));
            }
        });
    }

    /**
     * Create a GitLab Merge Request
     */
    private async createGitLabMR(
        repoInfo: RepoInfo,
        title: string,
        description: string,
        sourceBranch: string,
        targetBranch: string
    ): Promise<void> {
        const baseUrl = this.config.gitlabUrl || 'https://gitlab.com';
        const projectPath = encodeURIComponent(`${repoInfo.owner}/${repoInfo.repo}`);

        const response = await axios.post(
            `${baseUrl}/api/v4/projects/${projectPath}/merge_requests`,
            {
                source_branch: sourceBranch,
                target_branch: targetBranch,
                title: title,
                description: description
            },
            {
                headers: {
                    'PRIVATE-TOKEN': this.config.gitlabToken,
                    'Content-Type': 'application/json'
                }
            }
        );

        vscode.window.showInformationMessage(
            `Merge request created: ${response.data.web_url}`,
            'Open MR'
        ).then(selection => {
            if (selection === 'Open MR') {
                vscode.env.openExternal(vscode.Uri.parse(response.data.web_url));
            }
        });
    }

    /**
     * Create a Bitbucket Pull Request
     */
    private async createBitbucketPR(
        repoInfo: RepoInfo,
        title: string,
        description: string,
        sourceBranch: string,
        targetBranch: string
    ): Promise<void> {
        const auth = Buffer.from(
            `${this.config.bitbucketUsername}:${this.config.bitbucketToken}`
        ).toString('base64');

        const response = await axios.post(
            `https://api.bitbucket.org/2.0/repositories/${repoInfo.owner}/${repoInfo.repo}/pullrequests`,
            {
                title: title,
                description: description,
                source: {
                    branch: { name: sourceBranch }
                },
                destination: {
                    branch: { name: targetBranch }
                }
            },
            {
                headers: {
                    'Authorization': `Basic ${auth}`,
                    'Content-Type': 'application/json'
                }
            }
        );

        vscode.window.showInformationMessage(
            `Pull request created: ${response.data.links.html.href}`,
            'Open PR'
        ).then(selection => {
            if (selection === 'Open PR') {
                vscode.env.openExternal(vscode.Uri.parse(response.data.links.html.href));
            }
        });
    }

    /**
     * Get issues from the repository
     * Supports GitHub, GitLab, and Bitbucket
     */
    async getIssues(state: 'open' | 'closed' | 'all' = 'open'): Promise<any[]> {
        const remoteUrl = await this.getRemoteUrl();
        if (!remoteUrl) {
            throw new Error('No remote repository found');
        }

        const repoInfo = await this.parseRepoUrl(remoteUrl);
        if (!repoInfo) {
            throw new Error('Could not parse repository information');
        }

        const provider = repoInfo.provider;
        const token = this.getProviderToken(provider);

        if (!token) {
            throw new Error(`${provider} token not configured`);
        }

        try {
            switch (provider) {
                case 'github':
                    return await this.getGitHubIssues(repoInfo, state);
                case 'gitlab':
                    return await this.getGitLabIssues(repoInfo, state);
                case 'bitbucket':
                    return await this.getBitbucketIssues(repoInfo, state);
                default:
                    throw new Error(`Unsupported VCS provider: ${provider}`);
            }
        } catch (error: any) {
            console.error(`Failed to fetch issues from ${provider}:`, error);
            vscode.window.showErrorMessage(`Failed to fetch issues: ${error.message}`);
            throw error;
        }
    }

    /**
     * Get GitHub issues
     */
    private async getGitHubIssues(repoInfo: RepoInfo, state: 'open' | 'closed' | 'all'): Promise<any[]> {
        if (!this.octokit) {
            throw new Error('GitHub token not configured');
        }

        const response = await this.octokit.issues.listForRepo({
            owner: repoInfo.owner,
            repo: repoInfo.repo,
            state: state,
            per_page: 50
        });

        return response.data;
    }

    /**
     * Get GitLab issues
     */
    private async getGitLabIssues(repoInfo: RepoInfo, state: 'open' | 'closed' | 'all'): Promise<any[]> {
        const baseUrl = this.config.gitlabUrl || 'https://gitlab.com';
        const projectPath = encodeURIComponent(`${repoInfo.owner}/${repoInfo.repo}`);

        // Map state to GitLab format
        const gitlabState = state === 'all' ? undefined : state === 'open' ? 'opened' : 'closed';

        const response = await axios.get(
            `${baseUrl}/api/v4/projects/${projectPath}/issues`,
            {
                params: {
                    state: gitlabState,
                    per_page: 50
                },
                headers: {
                    'PRIVATE-TOKEN': this.config.gitlabToken
                }
            }
        );

        // Normalize GitLab response to match GitHub format
        return response.data.map((issue: any) => ({
            number: issue.iid,
            title: issue.title,
            body: issue.description,
            state: issue.state === 'opened' ? 'open' : 'closed',
            html_url: issue.web_url,
            user: { login: issue.author?.username || 'unknown' },
            created_at: issue.created_at,
            updated_at: issue.updated_at
        }));
    }

    /**
     * Get Bitbucket issues
     */
    private async getBitbucketIssues(repoInfo: RepoInfo, state: 'open' | 'closed' | 'all'): Promise<any[]> {
        const auth = Buffer.from(
            `${this.config.bitbucketUsername}:${this.config.bitbucketToken}`
        ).toString('base64');

        // Map state to Bitbucket format
        const stateQuery = state === 'all' ? '' :
            state === 'open' ? '&q=state="open" OR state="new"' :
            '&q=state="closed" OR state="resolved"';

        const response = await axios.get(
            `https://api.bitbucket.org/2.0/repositories/${repoInfo.owner}/${repoInfo.repo}/issues?pagelen=50${stateQuery}`,
            {
                headers: {
                    'Authorization': `Basic ${auth}`
                }
            }
        );

        // Normalize Bitbucket response to match GitHub format
        return response.data.values.map((issue: any) => ({
            number: issue.id,
            title: issue.title,
            body: issue.content?.raw || '',
            state: ['open', 'new'].includes(issue.state) ? 'open' : 'closed',
            html_url: issue.links?.html?.href || '',
            user: { login: issue.reporter?.username || 'unknown' },
            created_at: issue.created_on,
            updated_at: issue.updated_on
        }));
    }

    async checkRepositoryHealth(): Promise<{ issues: string[]; suggestions: string[] }> {
        const issues: string[] = [];
        const suggestions: string[] = [];

        try {
            // Check if repository is clean
            const status = await this.getStatus();
            if (status.files.length > 0) {
                issues.push(`${status.files.length} uncommitted changes`);
                suggestions.push('Consider committing or stashing changes');
            }

            // Check for untracked files
            if (status.not_added.length > 0) {
                issues.push(`${status.not_added.length} untracked files`);
                suggestions.push('Add important files to Git or update .gitignore');
            }

            // Check if ahead/behind remote (simplified check)
            try {
                const status = await this.git.status();
                if (status.ahead > 0) {
                    issues.push(`${status.ahead} commits ahead of remote`);
                    suggestions.push('Push changes to remote repository');
                }

                if (status.behind > 0) {
                    issues.push(`${status.behind} commits behind remote`);
                    suggestions.push('Pull latest changes from remote repository');
                }
            } catch (error) {
                // Remote tracking not available
            }

            // Check for stale branches (this would require more complex logic)
            try {
                const branches = await this.getBranches();
                const allBranches = Object.keys(branches.branches);
                if (allBranches.length > 10) {
                    suggestions.push('Consider cleaning up old branches');
                }
            } catch (error) {
                // Branch info not available
            }

        } catch (error) {
            issues.push(`Failed to check repository health: ${error}`);
        }

        return { issues, suggestions };
    }
}
