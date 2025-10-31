import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from '@/components/common_components/Dashboard';
import LandingPage from './components/common_components/LandingPage';
import CardDemo from './components/common_components/LogIn';
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
                  <Dashboard />
              } 
            />
            {/* Catch all route - redirect to appropriate page based on auth status */}
            {/* <Route path="*" element={<Navigate to="/" replace />} /> */}
          </Routes>
        </div>
      </Router>
  );
}

export default App;