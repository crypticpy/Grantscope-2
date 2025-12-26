import React, { useState, useEffect } from 'react';
import { User, Bell, Shield, Database } from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { LoadingButton } from '../components/ui/LoadingButton';

const Settings: React.FC = () => {
  const { user, signOut } = useAuthContext();
  const [profile, setProfile] = useState({
    display_name: '',
    department: '',
    role: '',
    preferences: {}
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [isSigningOut, setIsSigningOut] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const { data } = await supabase
        .from('users')
        .select('*')
        .eq('id', user?.id)
        .single();

      if (data) {
        setProfile({
          display_name: data.display_name || '',
          department: data.department || '',
          role: data.role || '',
          preferences: data.preferences || {}
        });
      }
    } catch (error) {
      console.error('Error loading profile:', error);
    }
  };

  const updateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const { error } = await supabase
        .from('users')
        .update(profile)
        .eq('id', user?.id);

      if (error) throw error;

      setMessage('Profile updated successfully!');
    } catch (error) {
      console.error('Error updating profile:', error);
      setMessage('Error updating profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOut();
    } catch (error) {
      console.error('Error signing out:', error);
      setIsSigningOut(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">Settings</h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Manage your account preferences and Foresight configuration.
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* Profile Settings */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center">
              <User className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900 dark:text-white">Profile</h2>
            </div>
          </div>
          <div className="p-6">
            <form onSubmit={updateProfile} className="space-y-6">
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Email Address
                  </label>
                  <input
                    type="email"
                    id="email"
                    value={user?.email || ''}
                    disabled
                    className="mt-1 block w-full border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm bg-gray-50 dark:bg-[#3d4176] dark:text-gray-300"
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Email cannot be changed. Contact your administrator if needed.
                  </p>
                </div>

                <div>
                  <label htmlFor="display_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Display Name
                  </label>
                  <input
                    type="text"
                    id="display_name"
                    value={profile.display_name}
                    onChange={(e) => setProfile({...profile, display_name: e.target.value})}
                    className="mt-1 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-white rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    placeholder="Your name"
                  />
                </div>

                <div>
                  <label htmlFor="department" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Department
                  </label>
                  <select
                    id="department"
                    value={profile.department}
                    onChange={(e) => setProfile({...profile, department: e.target.value})}
                    className="mt-1 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-white rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                  >
                    <option value="">Select Department</option>
                    <option value="Community Health">Community Health</option>
                    <option value="Mobility & Connectivity">Mobility & Connectivity</option>
                    <option value="Housing & Economic Stability">Housing & Economic Stability</option>
                    <option value="Economic Development">Economic Development</option>
                    <option value="Environmental Sustainability">Environmental Sustainability</option>
                    <option value="Cultural & Entertainment">Cultural & Entertainment</option>
                    <option value="City Manager's Office">City Manager's Office</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="role" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Role
                  </label>
                  <select
                    id="role"
                    value={profile.role}
                    onChange={(e) => setProfile({...profile, role: e.target.value})}
                    className="mt-1 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-white rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                  >
                    <option value="">Select Role</option>
                    <option value="Strategic Planner">Strategic Planner</option>
                    <option value="Department Head">Department Head</option>
                    <option value="Analyst">Analyst</option>
                    <option value="Manager">Manager</option>
                    <option value="Director">Director</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              {message && (
                <div className={`text-sm ${message.includes('Error') ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                  {message}
                </div>
              )}

              <div className="flex justify-end">
                <LoadingButton
                  type="submit"
                  loading={loading}
                  loadingText="Updating..."
                  className="shadow-sm"
                >
                  Update Profile
                </LoadingButton>
              </div>
            </form>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center">
              <Bell className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900 dark:text-white">Notifications</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">Email Notifications</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Receive email updates about your followed cards and workstreams.</p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 text-brand-blue focus:ring-brand-blue border-gray-300 dark:border-gray-600 rounded"
                  defaultChecked
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">Weekly Digest</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Receive a weekly summary of new intelligence relevant to your workstreams.</p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 text-brand-blue focus:ring-brand-blue border-gray-300 dark:border-gray-600 rounded"
                  defaultChecked
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">High Priority Alerts</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Get notified immediately about high-impact or high-velocity cards.</p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 text-brand-blue focus:ring-brand-blue border-gray-300 dark:border-gray-600 rounded"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Privacy & Security */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center">
              <Shield className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900 dark:text-white">Privacy & Security</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">Profile Visibility</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Allow other users to see your profile information.</p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 text-brand-blue focus:ring-brand-blue border-gray-300 dark:border-gray-600 rounded"
                  defaultChecked
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-white">Share Workstreams</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Allow colleagues to view and collaborate on your workstreams.</p>
                </div>
                <input
                  type="checkbox"
                  className="h-4 w-4 text-brand-blue focus:ring-brand-blue border-gray-300 dark:border-gray-600 rounded"
                />
              </div>
            </div>
          </div>
        </div>

        {/* System Information */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center">
              <Database className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900 dark:text-white">System Information</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Version:</span>
                <span className="text-gray-900 dark:text-white">Foresight v1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Last Updated:</span>
                <span className="text-gray-900 dark:text-white">December 23, 2025</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Support:</span>
                <span className="text-gray-900 dark:text-white">contact-foresight@austintexas.gov</span>
              </div>
            </div>
          </div>
        </div>

        {/* Account Actions */}
        <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">Account Actions</h2>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              <LoadingButton
                onClick={handleSignOut}
                variant="danger"
                loading={isSigningOut}
                loadingText="Signing out..."
                className="w-full"
              >
                Sign Out
              </LoadingButton>
              <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                Sign out of your Foresight account. You'll need to sign in again to access the system.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
