import * as vscode from 'vscode';
import * as path from 'path';
import simpleGit, { SimpleGit, StatusResult, BranchSummary } from 'simple-git';
import { Octokit } from '@octokit/rest';
import axios from 'axios';

interface GitConfig {
    gitEnabled: boolean;
    githubToken: string;
    autoCommitMessages: boolean;
    defaultBranch: string;
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
        
        if (config.githubToken) {
            this.octokit = new Octokit({
                auth: config.githubToken
            });
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

    async parseGitHubUrl(url: string): Promise<{ owner: string; repo: string } | null> {
        const patterns = [
            /github\.com[\/:]([^\/]+)\/([^\/\.]+)/,
            /github\.com\/([^\/]+)\/([^\/]+)\.git/
        ];

        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) {
                return { owner: match[1], repo: match[2] };
            }
        }

        return null;
    }

    async createPullRequest(title: string, body: string, base: string = 'main'): Promise<void> {
        if (!this.octokit) {
            throw new Error('GitHub token not configured');
        }

        const remoteUrl = await this.getRemoteUrl();
        if (!remoteUrl) {
            throw new Error('No remote repository found');
        }

        const repoInfo = await this.parseGitHubUrl(remoteUrl);
        if (!repoInfo) {
            throw new Error('Could not parse GitHub repository information');
        }

        const currentBranch = await this.getCurrentBranch();
        
        try {
            const response = await this.octokit.pulls.create({
                owner: repoInfo.owner,
                repo: repoInfo.repo,
                title: title,
                body: body,
                head: currentBranch,
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

        } catch (error: any) {
            console.error('Failed to create pull request:', error);
            vscode.window.showErrorMessage(`Failed to create pull request: ${error.message}`);
            throw error;
        }
    }

    async getIssues(state: 'open' | 'closed' | 'all' = 'open'): Promise<any[]> {
        if (!this.octokit) {
            throw new Error('GitHub token not configured');
        }

        const remoteUrl = await this.getRemoteUrl();
        if (!remoteUrl) {
            throw new Error('No remote repository found');
        }

        const repoInfo = await this.parseGitHubUrl(remoteUrl);
        if (!repoInfo) {
            throw new Error('Could not parse GitHub repository information');
        }

        try {
            const response = await this.octokit.issues.listForRepo({
                owner: repoInfo.owner,
                repo: repoInfo.repo,
                state: state,
                per_page: 50
            });

            return response.data;

        } catch (error: any) {
            console.error('Failed to fetch issues:', error);
            vscode.window.showErrorMessage(`Failed to fetch issues: ${error.message}`);
            throw error;
        }
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
