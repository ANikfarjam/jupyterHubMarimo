import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from '@/components/common_components/Dashboard';
import LandingPage from './components/common_components/LandingPage';
import ProtectedRoute from './components/ProtectRoute';

// Protected Route component

function App() {
  return (
      <Router>
        <div className="flex items-center justify-center">
          <Routes>
            <Route 
              path="/" 
              element={
                    <LandingPage />
              } 
            />
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
          </Routes>
        </div>
      </Router>
  );
}

export default App;