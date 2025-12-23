import React, { createContext, useContext } from 'react';
import type { AuthContextType } from '../App';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthContextProvider: React.FC<{ children: React.ReactNode; value: AuthContextType }> = ({ children, value }) => (
  <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
);

export const useAuthContext = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
};
