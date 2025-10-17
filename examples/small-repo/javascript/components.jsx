/**
 * React Components Module
 * 
 * This module contains reusable React components for the application.
 * It includes form components, UI elements, and layout components.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

/**
 * Loading Spinner Component
 * Displays a loading spinner with optional text
 */
export const LoadingSpinner = ({ size = 'medium', text = 'Loading...' }) => {
    const sizeClasses = {
        small: 'w-4 h-4',
        medium: 'w-8 h-8',
        large: 'w-12 h-12'
    };

    return (
        <div className="flex items-center justify-center space-x-2">
            <div className={`animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 ${sizeClasses[size]}`}></div>
            {text && <span className="text-gray-600">{text}</span>}
        </div>
    );
};

LoadingSpinner.propTypes = {
    size: PropTypes.oneOf(['small', 'medium', 'large']),
    text: PropTypes.string
};

/**
 * Button Component
 * Reusable button with different variants and states
 */
export const Button = ({ 
    children, 
    variant = 'primary', 
    size = 'medium', 
    disabled = false, 
    loading = false,
    onClick,
    type = 'button',
    className = '',
    ...props 
}) => {
    const baseClasses = 'inline-flex items-center justify-center font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors';
    
    const variantClasses = {
        primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
        secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
        danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
        outline: 'border border-gray-300 text-gray-700 hover:bg-gray-50 focus:ring-blue-500'
    };
    
    const sizeClasses = {
        small: 'px-3 py-1.5 text-sm',
        medium: 'px-4 py-2 text-sm',
        large: 'px-6 py-3 text-base'
    };
    
    const disabledClasses = disabled || loading ? 'opacity-50 cursor-not-allowed' : '';
    
    const buttonClasses = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${disabledClasses} ${className}`;

    return (
        <button
            type={type}
            className={buttonClasses}
            disabled={disabled || loading}
            onClick={onClick}
            {...props}
        >
            {loading && <LoadingSpinner size="small" text="" />}
            <span className={loading ? 'ml-2' : ''}>{children}</span>
        </button>
    );
};

Button.propTypes = {
    children: PropTypes.node.isRequired,
    variant: PropTypes.oneOf(['primary', 'secondary', 'danger', 'outline']),
    size: PropTypes.oneOf(['small', 'medium', 'large']),
    disabled: PropTypes.bool,
    loading: PropTypes.bool,
    onClick: PropTypes.func,
    type: PropTypes.oneOf(['button', 'submit', 'reset']),
    className: PropTypes.string
};

/**
 * Input Field Component
 * Reusable input field with label and error handling
 */
export const InputField = ({ 
    label, 
    type = 'text', 
    value, 
    onChange, 
    error, 
    placeholder,
    required = false,
    disabled = false,
    className = '',
    ...props 
}) => {
    const inputClasses = `
        block w-full px-3 py-2 border rounded-md shadow-sm placeholder-gray-400 
        focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm
        ${error ? 'border-red-300' : 'border-gray-300'}
        ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'}
        ${className}
    `;

    return (
        <div className="mb-4">
            {label && (
                <label className="block text-sm font-medium text-gray-700 mb-1">
                    {label}
                    {required && <span className="text-red-500 ml-1">*</span>}
                </label>
            )}
            <input
                type={type}
                value={value}
                onChange={onChange}
                placeholder={placeholder}
                disabled={disabled}
                className={inputClasses}
                {...props}
            />
            {error && (
                <p className="mt-1 text-sm text-red-600">{error}</p>
            )}
        </div>
    );
};

InputField.propTypes = {
    label: PropTypes.string,
    type: PropTypes.string,
    value: PropTypes.string.isRequired,
    onChange: PropTypes.func.isRequired,
    error: PropTypes.string,
    placeholder: PropTypes.string,
    required: PropTypes.bool,
    disabled: PropTypes.bool,
    className: PropTypes.string
};

/**
 * Modal Component
 * Reusable modal dialog with overlay
 */
export const Modal = ({ isOpen, onClose, title, children, size = 'medium' }) => {
    const sizeClasses = {
        small: 'max-w-md',
        medium: 'max-w-lg',
        large: 'max-w-2xl',
        xlarge: 'max-w-4xl'
    };

    useEffect(() => {
        const handleEscape = (event) => {
            if (event.keyCode === 27) {
                onClose();
            }
        };

        if (isOpen) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        }

        return () => {
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = 'unset';
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                {/* Overlay */}
                <div 
                    className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                    onClick={onClose}
                ></div>

                {/* Modal */}
                <div className={`inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:w-full ${sizeClasses[size]}`}>
                    {/* Header */}
                    {title && (
                        <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg leading-6 font-medium text-gray-900">
                                    {title}
                                </h3>
                                <button
                                    onClick={onClose}
                                    className="text-gray-400 hover:text-gray-600 focus:outline-none"
                                >
                                    <span className="sr-only">Close</span>
                                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Content */}
                    <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                        {children}
                    </div>
                </div>
            </div>
        </div>
    );
};

Modal.propTypes = {
    isOpen: PropTypes.bool.isRequired,
    onClose: PropTypes.func.isRequired,
    title: PropTypes.string,
    children: PropTypes.node.isRequired,
    size: PropTypes.oneOf(['small', 'medium', 'large', 'xlarge'])
};

/**
 * User Card Component
 * Displays user information in a card format
 */
export const UserCard = ({ user, onEdit, onDelete, showActions = true }) => {
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDelete = useCallback(async () => {
        if (window.confirm('Are you sure you want to delete this user?')) {
            setIsDeleting(true);
            try {
                await onDelete(user.id);
            } catch (error) {
                console.error('Delete failed:', error);
            } finally {
                setIsDeleting(false);
            }
        }
    }, [user.id, onDelete]);

    const getRoleColor = (role) => {
        const colors = {
            admin: 'bg-red-100 text-red-800',
            user: 'bg-blue-100 text-blue-800',
            guest: 'bg-gray-100 text-gray-800'
        };
        return colors[role] || colors.guest;
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
                        <span className="text-gray-600 font-medium">
                            {user.username.charAt(0).toUpperCase()}
                        </span>
                    </div>
                    <div>
                        <h3 className="text-lg font-medium text-gray-900">{user.username}</h3>
                        <p className="text-sm text-gray-500">{user.email}</p>
                    </div>
                </div>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleColor(user.role)}`}>
                    {user.role}
                </span>
            </div>

            <div className="space-y-2 text-sm text-gray-600">
                <div>
                    <span className="font-medium">Created:</span> {new Date(user.created_at).toLocaleDateString()}
                </div>
                {user.last_login && (
                    <div>
                        <span className="font-medium">Last Login:</span> {new Date(user.last_login).toLocaleDateString()}
                    </div>
                )}
                <div>
                    <span className="font-medium">Status:</span> 
                    <span className={`ml-1 ${user.is_active ? 'text-green-600' : 'text-red-600'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                </div>
            </div>

            {showActions && (
                <div className="mt-4 flex space-x-2">
                    <Button
                        variant="outline"
                        size="small"
                        onClick={() => onEdit(user)}
                    >
                        Edit
                    </Button>
                    <Button
                        variant="danger"
                        size="small"
                        loading={isDeleting}
                        onClick={handleDelete}
                    >
                        Delete
                    </Button>
                </div>
            )}
        </div>
    );
};

UserCard.propTypes = {
    user: PropTypes.shape({
        id: PropTypes.number.isRequired,
        username: PropTypes.string.isRequired,
        email: PropTypes.string.isRequired,
        role: PropTypes.string.isRequired,
        created_at: PropTypes.string.isRequired,
        last_login: PropTypes.string,
        is_active: PropTypes.bool.isRequired
    }).isRequired,
    onEdit: PropTypes.func,
    onDelete: PropTypes.func,
    showActions: PropTypes.bool
};

/**
 * Search Bar Component
 * Reusable search input with debounced onChange
 */
export const SearchBar = ({ onSearch, placeholder = 'Search...', debounceMs = 300 }) => {
    const [searchTerm, setSearchTerm] = useState('');

    // Debounced search function
    const debouncedSearch = useCallback(
        debounce((term) => {
            onSearch(term);
        }, debounceMs),
        [onSearch, debounceMs]
    );

    useEffect(() => {
        debouncedSearch(searchTerm);
    }, [searchTerm, debouncedSearch]);

    return (
        <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
            </div>
            <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder={placeholder}
            />
        </div>
    );
};

SearchBar.propTypes = {
    onSearch: PropTypes.func.isRequired,
    placeholder: PropTypes.string,
    debounceMs: PropTypes.number
};

// Utility function for debouncing (if not imported from utils)
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
