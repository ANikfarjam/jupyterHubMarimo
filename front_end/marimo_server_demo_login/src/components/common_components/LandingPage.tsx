import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "@/components/ui/button";
import MarimoLogo from "@/assets/logo.png";

export default function LandingPage() {
  const navigate = useNavigate();
  const { loginWithRedirect, isAuthenticated, isLoading } = useAuth0();
  const [loginError, setLoginError] = useState<string | null>(null);

  // Redirect logged-in users automatically
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard");
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = async () => {
    try {
      setLoginError(null);
      await loginWithRedirect();
    } catch (error) {
      console.error("Login error:", error);
      setLoginError("Failed to redirect to login. Please check your Auth0 configuration.");
    }
  };

  // Show loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center bg-gray-100 w-screen h-screen">
        <div className="text-center">
          <img src={MarimoLogo} alt="Marimo Logo" className="h-32 w-62 mx-auto mb-4" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center bg-gray-100 w-screen h-screen">
      <div className="text-center">
        <img src={MarimoLogo} alt="Marimo Logo" className="h-32 w-62 mx-auto mb-8" />
        
        {loginError && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md">
            {loginError}
          </div>
        )}
        
        <Button 
          onClick={handleLogin} 
          size="lg"
          className="px-8 py-2 text-lg"
        >
          Log In
        </Button>
      </div>
    </div>
  );
}