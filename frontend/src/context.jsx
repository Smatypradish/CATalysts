import { createContext, useContext, useState } from 'react';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [operator, setOperator] = useState(() => {
    const raw = sessionStorage.getItem('operator');
    return raw ? JSON.parse(raw) : null;
  });

  const login = (op) => {
    sessionStorage.setItem('operator', JSON.stringify(op));
    setOperator(op);
  };
  const logout = () => {
    sessionStorage.removeItem('operator');
    setOperator(null);
  };
  return (
    <AuthCtx.Provider value={{ operator, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
