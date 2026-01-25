import { useState, useEffect } from 'react';
import { Bot, RefreshCw, Server, Cloud, Cpu, Network, HardDrive, CheckCircle, XCircle } from 'lucide-react';
import { Button, Card, CardHeader, CardTitle, CardContent, Spinner, StatusIndicator } from '../components/ui';
import { useStatus, useConnection } from '../store';
import apiClient, { AgentInfo } from '../api/client';
import { clsx } from 'clsx';

export function AgentsPage() {
  const { health, agents, isLoading, setHealth, setAgents, setLoading } = useStatus();
  const { isOnline } = useConnection();
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const loadStatus = async () => {
    if (!isOnline) return;
    
    setLoading(true);
    try {
      const [healthData, agentData] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getAgentStatus(),
      ]);
      setHealth(healthData);
      setAgents(agentData);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to load status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [isOnline]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Agents & Services
          </h1>
          <p className="text-gray-500 dark:text-gray-400">
            Monitor the status of ContextForge agents and services.
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastRefresh && (
            <span className="text-sm text-gray-500">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <Button onClick={loadStatus} disabled={isLoading || !isOnline} variant="secondary">
            <RefreshCw className={clsx('w-4 h-4 mr-2', isLoading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Service Health */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Server className="w-5 h-5 inline mr-2" />
            Service Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && !health && (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          )}

          {health && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(health.services).map(([name, service]) => (
                <div
                  key={name}
                  className={clsx(
                    'p-4 rounded-lg border',
                    service.status === 'healthy'
                      ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
                      : 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20'
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium capitalize">{name.replace(/_/g, ' ')}</span>
                    {service.status === 'healthy' ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                  </div>
                  {service.latency_ms !== undefined && (
                    <span className="text-sm text-gray-500">{service.latency_ms}ms</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {!isOnline && (
            <div className="text-center py-8 text-gray-500">
              Unable to fetch service status while offline.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Agents List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              <Bot className="w-5 h-5 inline mr-2" />
              Agents
            </span>
            {agents && (
              <div className="flex gap-4 text-sm font-normal">
                <span className="flex items-center gap-1">
                  <Cpu className="w-4 h-4" />
                  {agents.local_agents} Local
                </span>
                <span className="flex items-center gap-1">
                  <Cloud className="w-4 h-4" />
                  {agents.remote_agents} Remote
                </span>
              </div>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && !agents && (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          )}

          {agents && (
            <div className="space-y-4">
              {Object.entries(agents.agents).map(([name, agent]) => (
                <AgentCard key={name} name={name} agent={agent} />
              ))}
            </div>
          )}

          {agents && Object.keys(agents.agents).length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No agents configured.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AgentCard({ name, agent }: { name: string; agent: AgentInfo }) {
  return (
    <div className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="font-medium text-gray-900 dark:text-gray-100">{name}</h4>
          <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              {agent.resolved_location === 'local' ? (
                <><Cpu className="w-3 h-3" /> Local</>
              ) : (
                <><Cloud className="w-3 h-3" /> Remote</>
              )}
            </span>
            <span className="capitalize">{agent.execution_hint}</span>
          </div>
        </div>
        <StatusIndicator 
          status="online" 
          label={agent.resolved_location} 
          showLabel={false} 
        />
      </div>
      
      <div className="mt-3 flex flex-wrap gap-2">
        {agent.capabilities.requires_filesystem && (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
            <HardDrive className="w-3 h-3" /> Filesystem
          </span>
        )}
        {agent.capabilities.requires_network && (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400">
            <Network className="w-3 h-3" /> Network
          </span>
        )}
      </div>
    </div>
  );
}

