/**
 * Login Form Component
 * Handles user authentication with JWT and CSRF protection
 */

import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

export const LoginForm: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login, isLoading, error } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username || !password) {
      return;
    }

    const success = await login(username, password);
    if (success) {
      console.log('Login successful');
      // Redirect or update UI as needed
    }
  };

  return (
    <div className="login-form-container">
      <div className="login-form-card">
        <h2 className="login-form-title">ContextForge Login</h2>
        
        {error && (
          <div className="login-form-error">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              disabled={isLoading}
              required
              autoComplete="username"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              disabled={isLoading}
              required
              autoComplete="current-password"
            />
          </div>
          
          <button 
            type="submit" 
            className="login-button"
            disabled={isLoading || !username || !password}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <div className="login-form-footer">
          <p className="text-sm text-gray-600">
            Default credentials: admin / admin123
          </p>
        </div>
      </div>
      
      <style>{`
        .login-form-container {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .login-form-card {
          background: white;
          padding: 2rem;
          border-radius: 8px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
          width: 100%;
          max-width: 400px;
        }
        
        .login-form-title {
          font-size: 1.5rem;
          font-weight: bold;
          text-align: center;
          margin-bottom: 1.5rem;
          color: #333;
        }
        
        .login-form-error {
          background: #fee;
          border: 1px solid #fcc;
          color: #c33;
          padding: 0.75rem;
          border-radius: 4px;
          margin-bottom: 1rem;
          font-size: 0.875rem;
        }
        
        .login-form {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        
        .form-group label {
          font-weight: 500;
          color: #555;
          font-size: 0.875rem;
        }
        
        .form-group input {
          padding: 0.75rem;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 1rem;
          transition: border-color 0.2s;
        }
        
        .form-group input:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .form-group input:disabled {
          background: #f5f5f5;
          cursor: not-allowed;
        }
        
        .login-button {
          padding: 0.75rem;
          background: #667eea;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 1rem;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
          margin-top: 0.5rem;
        }
        
        .login-button:hover:not(:disabled) {
          background: #5568d3;
        }
        
        .login-button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        
        .login-form-footer {
          margin-top: 1.5rem;
          text-align: center;
        }
        
        .text-sm {
          font-size: 0.875rem;
        }
        
        .text-gray-600 {
          color: #666;
        }
      `}</style>
    </div>
  );
};

export default LoginForm;

