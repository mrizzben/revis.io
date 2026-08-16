import { useState } from 'react';
import { configureClientAccess, disableClientAccess } from '../../api/endpoints/clientAccess';
import Input from '../ui/Input';
import Button from '../ui/Button';

interface ClientAccessCardProps {
  projectId: number;
}

export default function ClientAccessCard({ projectId }: ClientAccessCardProps) {
  const [password, setPassword] = useState('');
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleEnable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.trim().length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      const result = await configureClientAccess(projectId, password.trim());
      setLink(result.url);
      setPassword('');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to enable client access');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setError('');
    setIsLoading(true);
    try {
      const result = await configureClientAccess(projectId);
      setLink(result.url);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to rotate the link');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisable = async () => {
    setError('');
    setIsLoading(true);
    try {
      await disableClientAccess(projectId);
      setLink(null);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to disable client access');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Client Access</h3>
        <p className="text-xs text-gray-500 mt-1">
          Share a secure link + password so clients can review designs without signing up.
        </p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}

      {link ? (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Secure link</label>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={link}
                className="flex-1 min-w-0 px-2 py-1.5 text-xs border border-border bg-gray-50"
                onFocus={(e) => e.target.select()}
              />
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={() => navigator.clipboard?.writeText(link)}
              >
                Copy
              </Button>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              type="button"
              onClick={handleRegenerate}
              isLoading={isLoading}
            >
              Regenerate link
            </Button>
            <Button
              variant="danger"
              size="sm"
              type="button"
              onClick={handleDisable}
              isLoading={isLoading}
            >
              Disable
            </Button>
          </div>
          <p className="text-xs text-amber-600">
            Share the password with your client separately. Regenerating invalidates the old link.
          </p>
        </div>
      ) : (
        <form onSubmit={handleEnable} className="space-y-3">
          <Input
            label="Client access password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min 8 characters"
            required
            minLength={8}
            autoComplete="off"
          />
          <Button type="submit" isLoading={isLoading} className="w-full" size="sm">
            Enable client access
          </Button>
        </form>
      )}
    </div>
  );
}
